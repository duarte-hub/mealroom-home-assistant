"""Behaviour checks for planning, persistence, imports and HA ingress isolation."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'meal_planner'))
from app import create_app, valid_recipe, valid_backup
from planner import generate, empty_plan, shopping, eligible
from store import initial_state

WEEK='2026-10-26'

class PlannerTests(unittest.TestCase):
    def setUp(self): self.s=initial_state()

    def test_starter_recipes_validate(self):
        for recipe in self.s['recipes']:
            self.assertEqual(valid_recipe(recipe),recipe)

    def test_generation_enforces_budget_and_fills_seven_days(self):
        self.s['settings']['budget']=4500
        p=generate(self.s,WEEK,42)
        ids={r['id']:r for r in self.s['recipes']}
        self.assertEqual(len(p['days']),7)
        self.assertTrue(all(d['recipe_id'] in ids for d in p['days']))
        self.assertLessEqual(sum(ids[d['recipe_id']]['cost']*2 for d in p['days']),4500)

    def test_allergy_diet_time_and_dislikes_are_hard_filters(self):
        self.s['settings'].update(diet='vegan',allergens=['soy','peanuts'],max_minutes=35,dislikes=['mushroom'])
        p=generate(self.s,WEEK,4)
        ids={r['id']:r for r in self.s['recipes']}
        for d in p['days']:
            r=ids[d['recipe_id']]
            self.assertEqual(r['protein_type'],'vegan')
            self.assertLessEqual(r['minutes'],35)
            self.assertFalse(set(r['allergens'])&{'soy','peanuts'})
            self.assertTrue(eligible(r,self.s['settings']))

    def test_lock_survives_regeneration_even_when_preferences_change(self):
        p=empty_plan(WEEK);p['days'][0].update(recipe_id='salmon-couscous',locked=True)
        self.s['plans'][WEEK]=p;self.s['settings']['diet']='vegan'
        result=generate(self.s,WEEK,7)
        self.assertEqual(result['days'][0]['recipe_id'],'salmon-couscous')
        self.assertTrue(result['warnings'])

    def test_impossible_budget_raises_without_partial_plan(self):
        self.s['settings']['budget']=100
        with self.assertRaisesRegex(ValueError,'budget'): generate(self.s,WEEK,42)
        self.assertEqual(self.s['plans'],{})

    def test_no_eligible_recipe_does_not_ignore_filters(self):
        self.s['settings'].update(equipment=[],max_minutes=10)
        with self.assertRaisesRegex(ValueError,'No recipes'):generate(self.s,WEEK)

    def test_shopping_scales_and_combines_units_without_guessing(self):
        r=copy.deepcopy(self.s['recipes'][0]);r.update(id='test',servings=2)
        r['ingredients']=[dict(name='Rice',quantity=.25,unit='kg',category='Pantry'),dict(name='rice',quantity=50,unit='g',category='Pantry'),dict(name='Rice',quantity=1,unit='cup',category='Pantry')]
        self.s['recipes']=[r];self.s['settings']['household']=4
        p=empty_plan(WEEK);p['days'][0]['recipe_id']='test';self.s['plans'][WEEK]=p
        rows=shopping(self.s,WEEK)
        self.assertEqual(len(rows),2)
        self.assertEqual(next(i['quantity'] for i in rows if i['unit']=='g'),600)
        self.assertEqual(next(i['quantity'] for i in rows if i['unit']=='cup'),2)

class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=create_app(self.tmp.name);self.client=self.app.test_client()
        self.headers={'X-CSRF-Token':self.app.csrf_token}
    def mutate(self,path,data,method='POST'):
        return self.client.open(path,method=method,json=data,headers=self.headers)
    def get(self):return self.client.get('/api/state?week='+WEEK).get_json()

    def test_mutations_require_csrf(self):
        response=self.client.post('/api/plan/generate',json={'week':WEEK})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.get()['plans'],{})

    def test_ingress_rejects_direct_peer_and_spoofed_forwarded_headers(self):
        app=create_app(self.tmp.name,ingress_only=True);c=app.test_client()
        self.assertEqual(c.get('/api/state').status_code,403)
        self.assertEqual(c.get('/api/state',headers={'X-Forwarded-For':'172.30.32.2'}).status_code,403)
        self.assertEqual(c.get('/api/state',environ_base={'REMOTE_ADDR':'172.30.32.2'}).status_code,200)
        self.assertEqual(c.get('/healthz').status_code,200)

    def test_plan_and_shopping_check_persist_across_server_restart(self):
        self.assertEqual(self.mutate('/api/plan/generate',{'week':WEEK}).status_code,200)
        row=self.get()['shopping'][0]
        self.mutate('/api/shopping/check',{'week':WEEK,'key':row['key'],'checked':True},'PATCH')
        restarted=create_app(self.tmp.name).test_client().get('/api/state?week='+WEEK).get_json()
        self.assertEqual(len(restarted['plan']['days']),7)
        self.assertTrue(next(r for r in restarted['shopping'] if r['key']==row['key'])['checked'])

    def test_recipe_crud_favourite_and_note_round_trip(self):
        recipe=copy.deepcopy(self.get()['recipes'][0]);recipe['title']='Our <special> dinner'
        created=self.mutate('/api/recipes',recipe).get_json()['recipe'];rid=created['id']
        self.assertNotEqual(rid,recipe['id'])
        self.mutate('/api/recipes/'+rid+'/personal',{'favourite':True,'note':'More lemon','rating':4,'cooked':True},'PATCH')
        data=self.get();self.assertIn(rid,data['favourites']);self.assertEqual(data['ratings'][rid]['note'],'More lemon')
        self.assertEqual(self.mutate('/api/recipes/'+rid,created,'PUT').status_code,200)
        self.assertEqual(self.mutate('/api/recipes/'+rid,None,'DELETE').status_code,200)
        self.assertNotIn(rid,self.get()['favourites'])

    def test_invalid_restore_is_atomic_and_valid_backup_roundtrips(self):
        self.mutate('/api/plan/generate',{'week':WEEK})
        saved=self.client.get('/api/backup').get_json()
        corrupt=copy.deepcopy(saved);corrupt['plans'][WEEK]['days'][0]['recipe_id']='missing'
        self.assertEqual(self.mutate('/api/restore',corrupt).status_code,400)
        self.assertEqual(self.client.get('/api/backup').get_json(),saved)
        self.assertEqual(self.mutate('/api/restore',saved).status_code,200)
        self.assertEqual(self.get()['plan']['days'],saved['plans'][WEEK]['days'])

    def test_nonfinite_prices_and_bad_settings_rejected(self):
        r=self.get()['recipes'][0];r['cost']=float('nan')
        self.assertEqual(self.mutate('/api/recipes',r).status_code,400)
        settings=self.get()['settings'];settings['household']=0
        self.assertEqual(self.mutate('/api/settings',settings,'PUT').status_code,400)

    def test_swap_locked_meal_rejected(self):
        self.mutate('/api/plan/generate',{'week':WEEK})
        self.mutate('/api/plan/day',{'week':WEEK,'day':0,'locked':True},'PATCH')
        before=self.get()['plan']['days'][0]
        self.assertEqual(self.mutate('/api/plan/swap',{'week':WEEK,'day':0}).status_code,400)
        self.assertEqual(self.get()['plan']['days'][0],before)

    def test_pantry_and_extra_groceries_survive_export(self):
        self.mutate('/api/shopping/extras',{'week':WEEK,'name':'Coffee','quantity':250,'unit':'g','category':'Pantry'})
        self.mutate('/api/pantry',{'items':['Coffee']},'PUT')
        self.assertTrue(self.get()['shopping'][0]['pantry'])
        backup=self.client.get('/api/backup').get_json()
        self.assertEqual(valid_backup(backup)['extras'],backup['extras'])

    def test_frontend_urls_are_relative_for_ingress(self):
        html=self.client.get('/').get_data(as_text=True)
        self.assertNotIn('href="/static',html);self.assertNotIn('src="/static',html)
        self.assertIn('static/app.js',html)
        self.assertIn('default-src',self.client.get('/').headers['Content-Security-Policy'])

if __name__=='__main__':unittest.main()

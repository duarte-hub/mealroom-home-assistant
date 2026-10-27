"""Check source package assumptions before a Supervisor or Docker build."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET
import yaml

root=Path(__file__).resolve().parents[1]
app=root/'meal_planner'
config=yaml.safe_load((app/'config.yaml').read_text())
assert config['arch']==['aarch64','amd64']
assert config['ingress'] is True and config['ingress_port']==8099
assert config['environment']['INGRESS_ONLY']=='true'
assert not config.get('ports') and not config.get('host_network')
assert not config.get('hassio_api') and not config.get('privileged')
assert config['options']['household']>=1
assert config['version']=='0.1.0'
assert yaml.safe_load((root/'repository.yaml').read_text())['name']
assert yaml.safe_load((root/'compose.yaml').read_text())['services']['mealroom']['ports']==['127.0.0.1:8099:8099']
for recipe in json.loads((app/'recipes.json').read_text()):
    assert (app/'static/art'/f"{recipe['art']}.svg").is_file()
for image in (app/'static').rglob('*.svg'):
    ET.parse(image)
js=(app/'static/app.js').read_text()
assert 'https://' not in js and 'http://' not in js
assert "fetch(path," in js
assert '["/run-mealroom.sh"]' in (app/'Dockerfile').read_text()
assert 'su-exec mealroom:mealroom python' in (app/'run.sh').read_text()
print('Package metadata, ingress settings, relative UI requests and local SVG assets validated.')

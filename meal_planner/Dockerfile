FROM python:3.13-alpine

ARG BUILD_ARCH=amd64
LABEL io.hass.name="Mealroom" \
      io.hass.description="Local meal planning, recipes and shopping lists" \
      io.hass.type="addon" \
      io.hass.version="0.1.0" \
      io.hass.arch="${BUILD_ARCH}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    PORT=8099

RUN apk add --no-cache su-exec \
    && addgroup -g 1000 mealroom \
    && adduser -D -u 1000 -G mealroom mealroom \
    && mkdir -p /app /data \
    && chown mealroom:mealroom /data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py planner.py store.py run.py recipes.json ./
COPY templates ./templates
COPY static ./static
COPY run.sh /run-mealroom.sh
RUN chmod 755 /run-mealroom.sh
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=3)"
CMD ["/run-mealroom.sh"]

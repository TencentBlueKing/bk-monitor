ARG BKAI_INIT_IMAGE
FROM ${BKAI_INIT_IMAGE}

RUN python -c "from importlib.metadata import version; assert version('bkai-init') == '0.1.6', 'bkai-init 0.1.6 is required'"

WORKDIR /app
COPY --chown=10001:10001 package /app/package
COPY --chown=10001:10001 scripts /app/scripts

USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "/app/scripts/run_bkai.py"]
CMD ["validate"]

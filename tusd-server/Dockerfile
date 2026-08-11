# Approved upstream tag: tusproject/tusd:v1.8
FROM tusproject/tusd@sha256:04af04cbf28542d15f992a747c05199be11460e9eacf2c0721112c8bea4bb1c0

ARG SOURCE
ARG COMMIT_HASH
ARG COMMIT_ID
ARG BUILD_TIME
LABEL source=${SOURCE}
LABEL commit_hash=${COMMIT_HASH}
LABEL commit_id=${COMMIT_ID}
LABEL build_time=${BUILD_TIME}

ENTRYPOINT ["tusd", "-behind-proxy"]
CMD [ "--hooks-dir", "/srv/tusd-hooks" ]

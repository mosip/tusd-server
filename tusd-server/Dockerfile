FROM tusproject/tusd:v1.8

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

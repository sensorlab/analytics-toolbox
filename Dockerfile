# set base image (host OS)
FROM python:3.8

# set the working directory in the container
LABEL maintainer="Gregor Cerar <gregor.cerar@ijs.si>" 

ARG UID=1000 
ARG GID=1000
ARG UNAME=worker

# Suppress any manual intervention, configuring packets
ARG DEBIAN_FRONTEND=noninteractive

# copy the dependencies file to the working directory
WORKDIR /code

# Make RUN commands use `bash --login`:
SHELL ["/bin/bash", "--login", "-c"]

RUN : \
    && groupadd --non-unique --gid ${GID} ${UNAME} \
    && useradd -m --uid ${UID} --gid ${GID} -o -s /bin/bash ${UNAME} \
    && apt-get update -q \
    && apt-get install -y --no-install-recommends libhdf5-dev graphviz \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && :

# Upgrade system pip to the latest version
RUN python3 -m pip install --no-cache-dir -U pip

# Switch to unprivileged user
USER ${UID}:${GID}

# update PATH environment variable
ENV PATH=$PATH:/home/${UNAME}/.local/bin

# install dependencies
COPY requirements.txt .

RUN : \
    && python3 -m pip install --user --no-cache-dir -r requirements.txt \
    && python3 -m pip install --user --no-cache-dir SciencePlots \
    && :

CMD [ "/bin/bash" ]

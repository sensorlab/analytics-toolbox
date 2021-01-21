UID ?= $(shell id -u)
GID ?= $(shell id -g)
UNAME ?= toolbox

container:
	docker build \
		--build-arg UID=$(UID) \
		--build-arg GID=$(GID) \
		--build-arg UNAME=$(UNAME) \
		--file Dockerfile \
		--tag sensorlab/lqe \
		.
	docker run \
		-it \
		--rm \
		--name lqe \
		-v $(shell pwd):/code:z \
		sensorlab/lqe



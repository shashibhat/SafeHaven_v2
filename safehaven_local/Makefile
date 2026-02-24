.PHONY: demo-mock up-local up-frigate

demo-mock:
	cd safehaven-core && ./scripts/demo_mock.sh

up-local:
	docker-compose up --build

up-frigate:
	docker-compose --profile frigate up --build

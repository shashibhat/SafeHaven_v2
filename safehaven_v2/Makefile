.PHONY: lint-configs

lint-configs:
	ruby -e 'require "yaml"; ["frigate/config/config.yml", "deploy/frigate-host/config/frigate-host.yml", "safehaven-core/config/safehaven.yml"].each { |path| YAML.load_file(path); puts "#{path}: ok" }'

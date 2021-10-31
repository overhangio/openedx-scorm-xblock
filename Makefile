upgrade-vendor: ## Upgrade vendor js dependencies
	npm update
	npm install
	cp node_modules/renderjson/renderjson.js openedxscorm/static/js/vendor
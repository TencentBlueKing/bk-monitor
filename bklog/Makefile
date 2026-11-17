unittest:
	sh ./scripts/unit_test.sh

.PHONY: build-web
build-web:
	cd web && node scripts/build-web.mjs

sync_stag:
	sh ./scripts/git.sh sync_stag

sync_upstream:
	sh ./scripts/git.sh sync_upstream

translate:
	django-admin makemessages --extension py --ignore env_github && django-admin compilemessages

del_py_crypto:
	pip uninstall -y pycrypto
	pip uninstall -y pycryptodome
	pip install pycryptodome

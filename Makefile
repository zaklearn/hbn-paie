.PHONY: test integrity
test:          ## suite complète (dev : Python 3.12 + MySQL 8.4 éphémère)
	scripts/dev-test.sh
integrity:     ## contrôle d'intégrité du noyau gelé seul
	scripts/dev-test.sh tests/test_core_integrity.py

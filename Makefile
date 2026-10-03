PYTHON ?= venv/bin/python
LANGS  := es fr de it pt ja ru zh_Hans

.PHONY: help i18n i18n-extract i18n-clean-fuzzy i18n-compile collectstatic restart

help:
	@echo "Targets:"
	@echo "  i18n              extract → strip fuzzy markers → compile (full pipeline)"
	@echo "  i18n-extract      run makemessages --all"
	@echo "  i18n-clean-fuzzy  delete '#, fuzzy' markers from project .po files"
	@echo "  i18n-compile      run compilemessages"
	@echo "  collectstatic     run collectstatic --noinput"
	@echo "  restart           supervisorctl restart lostatnight-gunicorn"

# Full i18n pipeline. Run this after editing any template/JS string.
# Example: make i18n
i18n: i18n-extract i18n-clean-fuzzy i18n-compile
	@echo "i18n: pipeline finished."

i18n-extract:
	$(PYTHON) manage.py makemessages --all --ignore=venv --ignore=staticfiles --ignore=node_modules

# `makemessages` adds `#, fuzzy` flags to msgids that look similar to other
# already-translated strings. Django **ignores** msgstrs flagged fuzzy, so
# the page renders the English msgid even though the .po looks translated.
# Strip the markers so the inherited translations actually take effect.
# (If a translation is wrong, edit the .po manually and remove or fix it.)
i18n-clean-fuzzy:
	@for lang in $(LANGS); do \
		po="locale/$$lang/LC_MESSAGES/django.po"; \
		if [ -f "$$po" ]; then \
			sed -i '/^#, fuzzy$$/d' "$$po"; \
			echo "  cleaned $$po"; \
		fi; \
	done

i18n-compile:
	$(PYTHON) manage.py compilemessages

collectstatic:
	$(PYTHON) manage.py collectstatic --noinput

restart:
	sudo -n supervisorctl restart lostatnight-gunicorn

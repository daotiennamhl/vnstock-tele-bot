BRANCH = master
push:
	read -p "enter branch: " BRANCH; \
	git pull origin $$BRANCH; \
	sleep 1; \
	git add .; \
	git commit -m "update"; \
	sleep 1; \
	git push origin $$BRANCH
master:
	git pull origin main; \
	sleep 1; \
	git add .; \
	git commit -m "update"; \
	sleep 1; \
	git push origin main
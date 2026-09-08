BRANCH = master
push:
	read -p "enter branch: " BRANCH; \
	git pull origin $$BRANCH; \
	sleep 0.3; \
	git add .; \
	git commit -m "update"; \
	sleep 0.3; \
	git push origin $$BRANCH
master:
	git pull origin master; \
	sleep 0.3; \
	git add .; \
	git commit -m "update"; \
	sleep 0.3; \
	git push origin master
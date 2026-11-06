FROM nginxinc/nginx-unprivileged:1.29-alpine

USER root
# Base image packages lag behind Alpine security fixes.
RUN apk upgrade --no-cache

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html

USER 101
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]

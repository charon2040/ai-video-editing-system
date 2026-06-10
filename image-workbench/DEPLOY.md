# Image Workbench Deploy

This page is a static image workbench for Sub2API.

## Server Path

Upload `index.html` to:

```bash
/opt/image-workbench/index.html
```

## Caddy

Update `/opt/caddy-sub2api/Caddyfile`:

```caddy
api.apilane.xyz {
    encode zstd gzip

    handle_path /image* {
        root * /opt/image-workbench
        try_files {path} /index.html
        file_server
    }

    handle {
        reverse_proxy 127.0.0.1:8080
    }
}
```

Restart Caddy:

```bash
docker restart caddy-sub2api
```

Open:

```text
https://api.apilane.xyz/image
```

## Sub2API Custom Menu

In admin settings, add a custom menu item:

```text
Name: 图片工作台
URL: https://api.apilane.xyz/image
Visibility: User
Enabled: On
```

## Notes

- The page calls `/v1/images/generations` for text-to-image.
- The page calls `/v1/images/edits` when a reference image is selected.
- Users paste their own `sk-...` key. Do not hardcode an upstream key into this page.
- Image responses with `b64_json`, `base64`, `image_b64`, or `url` are supported.

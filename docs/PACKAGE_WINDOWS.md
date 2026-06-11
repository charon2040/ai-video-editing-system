# Windows Package Checklist

Before sending the project to another user:

1. Run `npm run build` in `clip_mvp/frontend`.
2. Confirm `clip_mvp/frontend/dist/index.html` exists.
3. Delete generated task data:
   - `clip_mvp/uploads`
   - `clip_mvp/audio`
   - `clip_mvp/outputs`
   - `clip_mvp/data/clip_mvp.db`
   - `clip_mvp/data/tmp`
4. Do not include `clip_mvp/.env`.
5. Include `clip_mvp/.env.example`.
6. Include `third_party` only if you want a large offline package.
7. If `third_party` is too large, send it separately or send model/runtime download instructions.

Recommended archive content:

```text
FUNASR/
  clip_mvp/
  third_party/
```

The current local `third_party` directory can be tens of GB. For online delivery, send it separately.

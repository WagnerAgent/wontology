import { build } from "esbuild";
await build({
  entryPoints: ["src/main.tsx"],
  bundle: true,
  minify: true,
  sourcemap: false,
  legalComments: "external",
  outfile: "../src/wontology/static/app.js",
  loader: { ".woff2": "file" },
  external: ["/fonts/*"],
  define: { "process.env.NODE_ENV": '"production"' },
  target: ["es2022"],
});

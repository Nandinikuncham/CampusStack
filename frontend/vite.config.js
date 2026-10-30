import { defineConfig, loadEnv } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");

  return {
    plugins: [tailwindcss()],
    input: {
      home: resolve(process.cwd(), "index.html"),
      login: resolve(process.cwd(), "pages/login.html"),
      studentRegistration: resolve(process.cwd(), "pages/register-student.html"),
      facultyRegistration: resolve(process.cwd(), "pages/register-faculty.html"),
      workspace: resolve(process.cwd(), "pages/workspace.html"),
      question: resolve(process.cwd(), "pages/question.html"),
    },
    server: {
      proxy: {
        "/api": {
          target: env.VITE_DJANGO_PROXY_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});

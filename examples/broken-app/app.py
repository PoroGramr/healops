from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

broken = False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global broken
        if self.path == "/break":
            broken = True
            try:
                raise RuntimeError("Demo application exception: broken endpoint")
            except RuntimeError:
                import traceback

                traceback.print_exc()
            self.respond(500, "Broken: demo exception\n")
        elif self.path == "/reset":
            broken = False
            self.respond(200, "Reset\n")
        elif self.path == "/health":
            self.respond(
                503 if broken else 200, "unhealthy\n" if broken else "healthy\n"
            )
        else:
            self.respond(
                200, "HealOps broken-app demo. GET /break to fail, /reset to recover.\n"
            )

    def respond(self, code, text):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(text.encode())


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()

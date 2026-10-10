# coding=utf-8
"""
    开发/测试用 mock embedding 服务：OpenAI /v1/embeddings 协议，纯标准库实现。
    伪向量 = 固定基向量 + 文本哈希扰动（确定性、任意查询都有可测相似度）。
    仅用于本地/CI 管线验证（celery→provider→pgvector 全链路），不代表真实语义质量。
    用法：python scripts/dev/embedding_mock.py [port=9401]
"""
import hashlib
import json
import math
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DIM = 1024


def embed(text: str) -> list:
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    out = [0.9] + [0.1 * ((seed[i % len(seed)] / 255.0) - 0.5) for i in range(1, DIM)]
    norm = math.sqrt(sum(x * x for x in out))
    return [x / norm for x in out]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.path.startswith("/v1/embeddings"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        inputs = body.get("input") or []
        if isinstance(inputs, str):
            inputs = [inputs]
        data = [
            {"object": "embedding", "index": i, "embedding": embed(str(t))}
            for i, t in enumerate(inputs)
        ]
        res = json.dumps({
            "object": "list", "data": data, "model": body.get("model", "mock"),
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(res)))
        self.end_headers()
        self.wfile.write(res)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9401
    print(f"mock embeddings on http://127.0.0.1:{port}/v1/embeddings (dim={DIM})")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()

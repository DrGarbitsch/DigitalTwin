"""Stands in for the device agent: records what the dataservice sends to its TCP port."""
import json
import socketserver
import sys
import time

OUT = sys.argv[1]


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        data = self.rfile.read()
        with open(OUT, 'a') as f:
            for message in json.loads(data):
                message['_at'] = time.time()
                f.write(json.dumps(message) + '\n')


socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer(('127.0.0.1', 7070), Handler).serve_forever()

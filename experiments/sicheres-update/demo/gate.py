"""Tiny Redis client and atomic maintenance gate, for the isolated experiment only."""
import socket


def call(host, port, *args):
    parts = [str(arg).encode() for arg in args]
    payload = b"*%d\r\n" % len(parts) + b"".join(
        b"$%d\r\n" % len(part) + part + b"\r\n" for part in parts
    )
    with socket.create_connection((host, port), timeout=2) as conn:
        conn.sendall(payload)
        stream = conn.makefile("rb")
        line = stream.readline()
        if not line.endswith(b"\r\n"):
            raise RuntimeError("Redis response incomplete")
        kind, value = line[:1], line[1:-2]
        if kind == b"-":
            raise RuntimeError("Redis command rejected")
        if kind == b":":
            return int(value)
        if kind == b"$":
            n = int(value)
            if n < 0:
                return None
            data = stream.read(n)
            if stream.read(2) != b"\r\n":
                raise RuntimeError("Redis response incomplete")
            return data.decode()
        if kind == b"+":
            return value.decode()
        raise RuntimeError("Unexpected Redis response")


ACCEPT = """
if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
if redis.call('SADD', KEYS[2], ARGV[1]) == 1 then return 1 end
return -1
"""
MAINTENANCE = """
if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
redis.call('SET', KEYS[1], ARGV[1])
return 1
"""
RELEASE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('DEL', KEYS[1])
return 1
"""


class Gate:
    def __init__(self, host, port):
        self.host, self.port = host, port

    def cmd(self, *args):
        return call(self.host, self.port, *args)

    def accept(self, task):
        return self.cmd("EVAL", ACCEPT, 2, "maintenance", "active", task)

    def finish(self, task):
        return self.cmd("SREM", "active", task)

    def begin(self, owner):
        return self.cmd("EVAL", MAINTENANCE, 1, "maintenance", owner)

    def count(self):
        return self.cmd("SCARD", "active")

    def release(self, owner):
        return self.cmd("EVAL", RELEASE, 1, "maintenance", owner)

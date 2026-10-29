#!/usr/bin/env python3
"""Fail closed unless RabbitMQ reports zero ready/unacknowledged messages.

Input is `rabbitmqctl list_queues -q name messages_ready messages_unacknowledged`.
Do not print queue names or output; other deployments may consider them private.
"""
import sys


def is_idle(output):
    lines = output.splitlines()
    if lines and lines[0].split() == ["name", "messages_ready", "messages_unacknowledged"]:
        lines = lines[1:]
    if not lines:
        return False
    for line in lines:
        fields = line.split()
        if len(fields) != 3 or not fields[1].isdigit() or not fields[2].isdigit():
            return False
        if int(fields[1]) or int(fields[2]):
            return False
    return True


if __name__ == "__main__":
    if not is_idle(sys.stdin.read()):
        print("Broker queues are busy or could not be checked.", file=sys.stderr)
        sys.exit(1)

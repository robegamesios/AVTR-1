"""Persistent, text-streaming Codex connection for a voice conversation."""

import asyncio
import contextlib
import json
import os
import tempfile
from collections import deque

INSTRUCTIONS = (
    "You are Jarvis, a friendly conversational voice assistant speaking aloud. "
    "Answer simple questions directly in one short sentence, usually under 20 words. "
    "Give extra detail only when requested or needed. Start with the answer. "
    "Use plain spoken text, no markdown, lists, stage directions, or emojis. "
    "Do not narrate your thinking. Do not use tools, access files, or run commands."
)


class CodexVoice:
    async def __aenter__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="avtr-conversation-")
        self.resources = contextlib.ExitStack()
        self.log = self.resources.enter_context(
            open(os.path.join(self.directory.name, "codex.log"), "wb")  # noqa: SIM115
        )
        self.sequence = 0
        self.notifications = deque()
        self.process = await asyncio.create_subprocess_exec(
            os.path.expanduser("~/.local/bin/codex"),
            "app-server",
            "-c",
            'web_search="disabled"',
            "-c",
            'model_reasoning_effort="low"',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=self.log,
            cwd=self.directory.name,
            limit=4 * 1024 * 1024,
        )
        try:
            await self.request(
                "initialize",
                {
                    "clientInfo": {"name": "avtr_voice", "version": "0.1.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            await self.send({"method": "initialized", "params": {}})
            result = await self.request(
                "thread/start",
                {
                    "model": os.environ.get("AVTR_LLM_MODEL", "gpt-6.1-sol"),
                    "cwd": self.directory.name,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "ephemeral": True,
                    "baseInstructions": INSTRUCTIONS,
                    "config": {"model_reasoning_effort": os.environ.get("AVTR_LLM_EFFORT", "low")},
                },
            )
            self.thread_id = result["thread"]["id"]
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        await self.process.stdin.drain()

    async def read(self):
        line = await asyncio.wait_for(self.process.stdout.readline(), 120)
        if not line:
            raise RuntimeError("Codex voice connection closed")
        return json.loads(line)

    async def request(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        await self.send({"id": request_id, "method": method, "params": params})
        while True:
            message = await self.read()
            if message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message["result"]
            await self.route(message)

    async def route(self, message):
        if "id" in message and "method" in message:
            # This is a text-only voice client; decline unexpected tool requests.
            await self.send(
                {
                    "id": message["id"],
                    "error": {
                        "code": -32601,
                        "message": "Tools are unavailable in voice conversation",
                    },
                }
            )
        else:
            self.notifications.append(message)

    async def stream(self, text):
        result = await self.request(
            "turn/start",
            {
                "threadId": self.thread_id,
                "input": [{"type": "text", "text": text, "text_elements": []}],
                "effort": os.environ.get("AVTR_LLM_EFFORT", "low"),
            },
        )
        turn_id = result["turn"]["id"]
        try:
            while True:
                if self.notifications:
                    message = self.notifications.popleft()
                else:
                    message = await self.read()
                if "id" in message and "method" in message:
                    await self.route(message)
                    continue
                params = message.get("params", {})
                if params.get("threadId") != self.thread_id:
                    continue
                if (
                    message.get("method") == "item/agentMessage/delta"
                    and params.get("turnId") == turn_id
                ):
                    yield params["delta"]
                elif message.get("method") == "turn/completed" and params["turn"]["id"] == turn_id:
                    turn = params["turn"]
                    if turn["status"] != "completed":
                        raise RuntimeError(str(turn.get("error") or turn["status"]))
                    return
        except BaseException:
            with contextlib.suppress(Exception):
                await self.request(
                    "turn/interrupt", {"threadId": self.thread_id, "turnId": turn_id}
                )
            raise

    async def __aexit__(self, *_):
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.resources.close()
        self.directory.cleanup()

"""SEED-AI Interactive Terminal Chat

Run this script to chat live with SEED powered by local Qwen3 offline inference.
Type your prompt in Egyptian Arabic or English. Type 'exit' or 'quit' to stop.
"""

import sys
import os

sys.path.insert(0, r"D:\SEED-AI")

from core.application import SeedApplication


def main():
    print("=" * 60)
    print("SEED-AI INTERACTIVE TERMINAL CHAT (Offline Qwen3)")
    print("Type 'exit' or 'quit' to end the session.")
    print("=" * 60)

    try:
        app = SeedApplication()
    except Exception as e:
        print(f"Error initializing SeedApplication: {e}")
        return

    while True:
        try:
            user_input = input("\nأنت (User): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nمع السلامة!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "خروج"):
            print("\nمع السلامة! نتمنى لك يوم سعيد مع SEED.")
            break

        print("\nSEED يفكر ويجيب...")
        try:
            result = app.seed_request(user_input)
            print(f"\nSEED: {result.response}")
            if result.status != "completed":
                print(f"[Status: {result.status}]")
        except Exception as error:
            print(f"\n[خطأ أثناء التنفيذ: {error}]")


if __name__ == "__main__":
    main()

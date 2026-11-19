import argparse
import json

from controls_assistant.agent_loop import ask, make_client
from controls_assistant.config import load_settings


def main():
    parser = argparse.ArgumentParser(description="Ask the Controls Assistant a question.")
    parser.add_argument("question")
    parser.add_argument("--model", help="Model ID. Defaults to DEFAULT_MODEL_ID or MODEL_ID_A.")
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Print tool calls and usage.")
    args = parser.parse_args()

    settings = load_settings()
    client = make_client(settings.profile, settings.region)
    result = ask(client, args.model or settings.default_model_id, args.question, use_tools=not args.no_tools)

    print(result.answer)
    if args.verbose:
        print("---")
        print(f"model={result.model_id} stop={result.stop_reason} latency_ms={result.latency_ms:.0f}")
        print(f"tokens in={result.input_tokens} out={result.output_tokens}")
        for call in result.tool_calls:
            print("tool:", json.dumps(call))


if __name__ == "__main__":
    main()

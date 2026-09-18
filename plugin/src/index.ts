// SPDX-License-Identifier: Apache-2.0
// Newly authored against the public LM Studio SDK interfaces.
import { createConfigSchematics, GeneratorController, Chat, PluginContext } from "@lmstudio/sdk";

const config = createConfigSchematics()
  .field("model", "select", {
    displayName: "Model",
    options: [
      { value: "bonsai-2", displayName: "Bonsai 2 (native)" },
      { value: "orcabonsai-2", displayName: "OrcaBonsai (MLX)" },
    ],
  }, "bonsai-2")
  .field("reasoning", "select", {
    displayName: "Reasoning",
    options: ["off", "low", "medium", "xhigh"],
  }, "off")
  .build();

const endpoints = createConfigSchematics()
  .field("bonsai", "string", { displayName: "Bonsai endpoint" }, "http://127.0.0.1:18124/v1")
  .field("orca", "string", { displayName: "Orca endpoint" }, "http://127.0.0.1:18123/v1")
  .build();

function localEndpoint(value: string): string {
  const url = new URL(value);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) {
    throw new Error("This adapter accepts loopback HTTP endpoints only.");
  }
  return value.replace(/\/+$/, "");
}

async function generate(ctl: GeneratorController, history: Chat): Promise<void> {
  const settings = ctl.getPluginConfig(config);
  const servers = ctl.getGlobalPluginConfig(endpoints);
  const isOrca = settings.get("model") === "orcabonsai-2";
  const effort = settings.get("reasoning");
  try {
    if (ctl.getToolDefinitions().length) {
      throw new Error("This release supports text chat. Turn off integrations before sending.");
    }
    const messages = history.getMessagesArray().map(message => {
      if (message.getRole() === "tool") throw new Error("Start a new text-only chat; this history contains tool results.");
      return { role: message.getRole(), content: message.getText() };
    });
    const base = localEndpoint(servers.get(isOrca ? "orca" : "bonsai"));
    const response = await fetch(`${base}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: ctl.abortSignal,
      body: JSON.stringify({
        model: isOrca ? "orcabonsai" : "bonsai-2",
        messages, stream: true,
        enable_thinking: effort !== "off",
        reasoning_effort: effort === "off" ? undefined : effort,
        chat_template_kwargs: { enable_thinking: effort !== "off", reasoning_effort: effort === "off" ? "low" : effort },
        // No default output-token budget; Stop cancels the HTTP request.
      }),
    });
    if (!response.ok) throw new Error(`Server ${response.status}: ${await response.text()}`);
    if (!response.body) throw new Error("Server returned no response stream.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";
    let doneMarker = false;
    try {
      while (!doneMarker) {
        const { value, done } = await reader.read();
        pending += decoder.decode(value, { stream: !done });
        const lines = pending.split("\n");
        pending = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (data === "[DONE]") { doneMarker = true; break; }
          if (!data) continue;
          const event = JSON.parse(data);
          if (event.error) throw new Error(event.error.message || "Inference failed");
          const choice = event.choices?.[0];
          if (choice?.delta?.content) ctl.fragmentGenerated(choice.delta.content);
          if (choice?.delta?.reasoning_content) {
            ctl.fragmentGenerated(choice.delta.reasoning_content, { reasoningType: "reasoning" });
          }
          if (choice?.finish_reason === "length") throw new Error("The upstream server stopped at an output limit.");
        }
        if (done) {
          if (!doneMarker) throw new Error("The connection ended before the server finished its response.");
          break;
        }
      }
    } finally {
      await reader.cancel();
    }
  } catch (error) {
    if (ctl.abortSignal.aborted) return;
    const message = error instanceof Error ? error.message : String(error);
    ctl.fragmentGenerated(`\n\n**Adapter error:** ${message}\nIf a server is unavailable, open Launch.command.`);
  }
}

export function main(context: PluginContext): void {
  context.withConfigSchematics(config).withGlobalConfigSchematics(endpoints).withGenerator(generate);
}

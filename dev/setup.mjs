// Prepares the throwaway Home Assistant: onboarding, dev user and one config entry of the integration.
// Idempotent; run via `dev/ha.sh`. Dev credentials: dev / dev. Requires Node 22+ (global fetch).
// Usage: node dev/setup.mjs [base-url] [domain]
const base = (process.argv[2] ?? "http://localhost:8123").replace(/\/$/, "");
const domain = process.argv[3];
if (!domain) throw new Error("Pass the integration domain as the second argument (dev/ha.sh does it)");
const clientId = `${base}/`;
const USER = { name: "Dev", username: "dev", password: "dev", language: "en" };
// Answers for the first config flow step. Adapt them to the fields of your config flow.
const FLOW_INPUT = { name: "Dev" };

const json = async (path, init = {}) => {
  const response = await fetch(base + path, init);
  const text = await response.text();
  if (!response.ok) throw new Error(`${init.method ?? "GET"} ${path} → ${response.status} ${text}`);
  return text ? JSON.parse(text) : {};
};
const post = (path, body, token) =>
  json(path, {
    method: "POST",
    headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
const get = (path, token) => json(path, { headers: { authorization: `Bearer ${token}` } });

async function waitForHa() {
  for (let i = 0; i < 120; i++) {
    try {
      const response = await fetch(`${base}/api/onboarding`);
      if (response.status === 404) return []; // up, and onboarding is finished (HA stops serving it)
      if (response.ok) return await response.json();
    } catch {
      // not reachable yet
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error("Home Assistant did not come up in 4 minutes (see `dev/ha.sh logs`)");
}

async function exchange(code) {
  const form = new URLSearchParams({ grant_type: "authorization_code", code, client_id: clientId });
  return (await json("/auth/token", { method: "POST", body: form })).access_token;
}

async function login() {
  const flow = await post("/auth/login_flow", {
    client_id: clientId,
    handler: ["homeassistant", null],
    redirect_uri: clientId,
  });
  const result = await post(`/auth/login_flow/${flow.flow_id}`, {
    client_id: clientId,
    username: USER.username,
    password: USER.password,
  });
  if (result.type !== "create_entry") throw new Error("Dev login failed (wrong credentials? try `dev/ha.sh reset`)");
  return exchange(result.result);
}

async function onboard(steps) {
  const pending = new Set(steps.filter((s) => !s.done).map((s) => s.step));
  if (pending.has("user")) {
    await post("/api/onboarding/users", { client_id: clientId, ...USER });
    console.log("Created dev user (dev / dev)");
  }
  const token = await login();
  if (pending.has("core_config")) await post("/api/onboarding/core_config", {}, token);
  if (pending.has("analytics")) await post("/api/onboarding/analytics", {}, token);
  if (pending.has("integration")) {
    await post("/api/onboarding/integration", { client_id: clientId, redirect_uri: `${clientId}?auth_callback=1` }, token);
  }
  return token;
}

// Adds one entry of the integration through its own config flow (so the flow is exercised too).
async function addEntry(token) {
  const entries = await get("/api/config/config_entries/entry", token);
  if (entries.some((entry) => entry.domain === domain)) return console.log(`${domain} is already configured`);

  let step = await post("/api/config/config_entries/flow", { handler: domain, show_advanced_options: false }, token);
  if (step.type === "form") {
    step = await post(`/api/config/config_entries/flow/${step.flow_id}`, FLOW_INPUT, token);
  }
  if (step.type !== "create_entry") {
    throw new Error(`Config flow did not finish: ${JSON.stringify(step)} (adapt FLOW_INPUT in dev/setup.mjs)`);
  }
  console.log(`Configured ${domain}`);
}

const steps = await waitForHa();
const token = steps.some((s) => !s.done) ? await onboard(steps) : await login();
await addEntry(token);

console.log(`\nReady: ${base}  (user: ${USER.username} / password: ${USER.password})`);
console.log("After changing the code run `dev/ha.sh restart`; follow the logs with `dev/ha.sh logs`.");

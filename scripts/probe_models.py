import json, re, sys, time, urllib.request, urllib.error
env = dict(re.fullmatch(r"([A-Z_][A-Z0-9_]*)=(\S+)", l.strip()).groups() for l in open(".env") if re.fullmatch(r"[A-Z_][A-Z0-9_]*=\S+", l.strip()))
KEY = env["OPENROUTER_API_KEY"]
payload = {"questions": {
  "is_bug": {"type": "noul", "instructions": "Is the customer reporting a software defect?",
             "criteria": {"true": "The customer describes broken or unexpected product behavior.", "false": "The customer is asking a question or requesting a feature."}},
  "team": {"type": "choice", "instructions": "Which team should own this ticket?",
           "criteria": {"account": "Login, permissions, or profile issues.", "frontend": "Rendering, layout, or browser compatibility issues.", "payments": "Checkout, billing, or payment processing issues."}}},
  "state": {"customer_tier": "enterprise", "ticket": "My checkout page shows a blank screen after I click Pay. I have tried two browsers."}}
for model in sys.argv[1:]:
    body = dict(payload, model=model)
    req = urllib.request.Request("https://openrouter.ai/api/alpha/decisions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
        a = d.get("answers", {})
        print(f"OK   {model:34s} -> {d.get('model')} via {d.get('provider')} | {time.time()-t0:.2f}s | cost ${d.get('usage',{}).get('cost')} | is_bug={a.get('is_bug',{}).get('noul')} team={a.get('team',{}).get('probabilities')}")
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:160].replace("\n", " ")
        print(f"FAIL {model:34s} HTTP {e.code} {msg}")
    except Exception as e:
        print(f"FAIL {model:34s} {type(e).__name__} {str(e)[:100]}")

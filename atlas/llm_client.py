"""
ATLAS LLM client, talks to OpenRouter only, returns plain text.
"""
import os
import json
import time
import requests
from typing import Optional, Dict, Any, List

#configuration
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_MODELS = {
    "annotation": "anthropic/claude-sonnet-4.5",
    "validation": "anthropic/claude-sonnet-4.5",
    "formatting": "google/gemini-2.5-flash",
    "scoring": "anthropic/claude-sonnet-4.5",
    "reporting": "google/gemini-2.5-flash",
    "annotation_boost": "anthropic/claude-sonnet-4.5",
    "rag": "anthropic/claude-sonnet-4.5",
    "default": "anthropic/claude-sonnet-4.5",
}

#usage tracking
_USAGE_LOG: List[Dict[str, Any]] = []

def reset_usage() -> None:
  """Clear the in-process usage log."""
  _USAGE_LOG.clear()

def get_usage_summary() -> Dict[str, Any]:
  """Return totals across all calls in this session."""
  summary = {
      "n_calls": len(_USAGE_LOG), #总调用次数
      "prompt_tokens": 0, #输入token总数
      "completion_tokens": 0, #输出token总数
      "total_tokens": 0,
      "cost_usd": 0.0,
      "by_model": {}, #按模型分类的详细消耗
  }

  for entry in _USAGE_LOG:
    model = entry["model"]

    bm = summary["by_model"].setdefault(
        model,
        {
            "n_calls":0,
            "prompt_tokens":0,
            "completion_tokens":0,
            "total_tokens":0,
            "cost_usd": 0.0,
        }
    )
    bm["n_calls"] +=1

    #累加各项token指标
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
      value = entry.get(k,0)
      summary[k] += value
      bm[k] += value

    #累加费用
    cost = entry.get("cost_usd") or 0.0
    summary["cost_usd"] += cost
    bm["cost_usd"] += cost
  
  return summary

#main entry point
def call_llm(
    user_prompt: str,
    *,
    system_prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    agent: str = "default",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
    timeout: int = 180,
) -> str:
    """
    Send a prompt to OpenRouter and return the model's text response.
    """
    
    chosen_model = model or DEFAULT_MODELS.get(agent, DEFAULT_MODELS["default"])

    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY not found. Set it in Colab or pass api_key directly.")
    
    if messages is None:
      messages = []

      if system_prompt:
        messages.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )

      messages.append(
          {
              "role": "user",
              "content": user_prompt,
          }
      )
    #构造api请求负载
    payload = {
        "model": chosen_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    try:
      #发送post请求
      resp = requests.post(
          OPENROUTER_URL,
          headers=headers,
          data=json.dumps(payload),
          timeout=timeout,
      )
      resp.raise_for_status()

    except requests.HTTPError as e:
      _explain_http_error(e, chosen_model)
      raise

    except requests.Timeout:
      raise TimeoutError(
          f"Openrouter timed out after {timeout}s for model '{chosen_model}'."

      )
    
    #解析结果
    data = resp.json()
    usage = data.get("usage") or {}

    #记录本次消耗到日志中
    _USAGE_LOG.append(
        {
            "timestamp": time.time(),
            "model": chosen_model,
            "agent": agent,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cost_usd": usage.get("cost"),
        }

    )

    #提取文本内容
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or ""

def _explain_http_error(e: requests.HTTPError, model:str) -> None:

  #常见错误
  status = e.response.status_code if e.response is not None else None
  body = e.response.text if e.response is not None else ""

  if status == 401:
    print("401 Unauthorized: your OpenRouter API key is invalid or missing.")
  elif status == 402:
    print("402 Payment required: your OpenRouter account may be out of credits.")
  elif status == 404:
    print(f"404 Not Found: model '{model}' may not exist on OpenRouter.")
  elif status == 429:
    print("429 Rate limit: wait a moment or reduce parallel calls.")
  elif status and status >= 500:
    print(f"{status} OpenRouter server error: usually transient.")
  if body:
    print(f"Body: {body[:300]}")

#测试运行块
if __name__ == "__main__":
  reply = call_llm(
      "Say 'ATLAS online' and nothing else.",
      model="google/gemini-2.5-flash",
      max_tokens=20,
  )

  print(f"Reply: {reply!r}")
  print(f"Usage: {get_usage_summary()}")


    

    

#!/usr/bin/env python3
"""
OpenClaw 模型管理 Skill

支持六种操作：
1. 添加模型（验证 + 写入配置）
2. 删除模型（清理所有引用 + 修复默认模型）
3. 删除供应商（删除旗下所有模型并清理引用）
4. 获取模型列表（从 API 查询）
5. 测试模型可用性
6. 修改供应商密钥

缺失信息时输出 MISSING_INFO 提示，供 AI 代理询问用户。
"""

import json
import os
import requests
from pathlib import Path


CONFIG_PARSE_ERROR_KEY = "__config_parse_error__"


def _is_config_invalid(cfg: dict) -> bool:
    return bool(cfg.get(CONFIG_PARSE_ERROR_KEY, False))


def _normalize_api_type(api_type: str) -> str:
    v = (api_type or "").strip().lower()
    if v in ("", "openai", "openai-chat", "openai-completions"):
        return "openai-completions"
    if v in ("anthropic", "claude", "anthropic-messages"):
        return "anthropic-messages"
    return v


# ============================================================
# 配置读写
# ============================================================

def get_config_path() -> Path:
    return Path.home() / ".openclaw" / "openclaw.json"


def read_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return _empty_config()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 兼容带 // 注释的配置
            lines = []
            for line in content.split('\n'):
                in_str, qi, i = False, None, 0
                while i < len(line):
                    c = line[i]
                    if not in_str and c in ('"', "'"):
                        in_str, qi = True, c
                    elif in_str and c == qi and (i == 0 or line[i - 1] != '\\'):
                        in_str = False
                    elif not in_str and i < len(line) - 1 and line[i:i+2] == '//':
                        line = line[:i]
                        break
                    i += 1
                lines.append(line)
            return json.loads('\n'.join(lines))
    except Exception as e:
        print(f"[警告] 读取配置失败: {e}")
        cfg = _empty_config()
        cfg[CONFIG_PARSE_ERROR_KEY] = True
        return cfg


def save_config(cfg: dict) -> bool:
    if _is_config_invalid(cfg):
        print("[错误] 配置读取失败，已阻止写入以避免覆盖原配置")
        return False

    cfg = {k: v for k, v in cfg.items() if k != CONFIG_PARSE_ERROR_KEY}

    path = get_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[错误] 保存配置失败: {e}")
        return False


def backup_config():
    path = get_config_path()
    if not path.exists():
        return None
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = path.parent / f"openclaw.json.bak.{ts}"
        import shutil
        shutil.copy2(path, bak)
        return bak
    except Exception:
        return None


def _empty_config() -> dict:
    return {
        "models": {"providers": {}},
        "agents": {"defaults": {"model": {"fallbacks": []}, "models": {}}}
    }


def get_provider_info(name: str):
    cfg = read_config()
    return cfg.get("models", {}).get("providers", {}).get(name)


def list_providers():
    cfg = read_config()
    return list(cfg.get("models", {}).get("providers", {}).keys())


def get_provider_models(name: str) -> list[dict]:
    p = get_provider_info(name)
    if not p:
        return []
    return p.get("models", [])


def get_default_model() -> str:
    cfg = read_config()
    fb = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("fallbacks", [])
    return fb[0] if fb else ""


def _get_default_model_from_cfg(cfg: dict) -> str:
    fb = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("fallbacks", [])
    return fb[0] if fb else ""


def _first_available_model_ref(providers: dict, removed_refs: set[str] | None = None, removed_prefixes: set[str] | None = None) -> str:
    removed_refs = removed_refs or set()
    removed_prefixes = removed_prefixes or set()

    def _is_removed(model_ref: str) -> bool:
        if model_ref in removed_refs:
            return True
        return any(model_ref.startswith(prefix) for prefix in removed_prefixes)

    for provider_name, provider in providers.items():
        for model in provider.get("models", []):
            model_id = model.get("id", "")
            if not model_id:
                continue
            model_ref = f"{provider_name}/{model_id}"
            if not _is_removed(model_ref):
                return model_ref
    return ""


def _clean_default_references(
    cfg: dict,
    removed_refs: set[str] | None = None,
    removed_prefixes: set[str] | None = None,
    promoted_default: str = "",
    prefer_first_available: bool = False,
) -> str:
    removed_refs = removed_refs or set()
    removed_prefixes = removed_prefixes or set()

    cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {}).setdefault("fallbacks", [])
    cfg["agents"]["defaults"].setdefault("models", {})

    fallbacks = cfg["agents"]["defaults"]["model"]["fallbacks"]
    current_default = fallbacks[0] if fallbacks else ""

    def _should_remove(model_ref: str) -> bool:
        if model_ref in removed_refs:
            return True
        return any(model_ref.startswith(prefix) for prefix in removed_prefixes)

    cleaned_fallbacks = [ref for ref in fallbacks if not _should_remove(ref)]
    cfg["agents"]["defaults"]["models"] = {
        k: v for k, v in cfg["agents"]["defaults"]["models"].items()
        if not _should_remove(k)
    }

    if not promoted_default and current_default and _should_remove(current_default):
        if prefer_first_available:
            promoted_default = _first_available_model_ref(cfg.get("models", {}).get("providers", {}), removed_refs, removed_prefixes)
        else:
            promoted_default = cleaned_fallbacks[0] if cleaned_fallbacks else ""

    if promoted_default:
        cleaned_fallbacks = [ref for ref in cleaned_fallbacks if ref != promoted_default]
        cleaned_fallbacks.insert(0, promoted_default)

    cfg["agents"]["defaults"]["model"]["fallbacks"] = cleaned_fallbacks
    return promoted_default


def _provider_model_refs(provider_name: str, provider: dict) -> set[str]:
    prefix = f"{provider_name}/"
    refs = set()
    for model in provider.get("models", []):
        model_id = model.get("id", "")
        if model_id:
            refs.add(f"{prefix}{model_id}")
    return refs


def _join_url(base, suffix):
    """拼接 base_url 和 suffix，只去重 /v1"""
    base = base.rstrip('/')
    suffix = suffix.rstrip('/')

    # 如果 base 末尾是 /v1 且 suffix 开头是 /v1/，去掉 suffix 开头的 /v1
    # base=.../openai/v1 + /v1/chat -> .../openai/v1/chat
    if suffix.startswith('/v1/') and base.endswith('/v1'):
        suffix = suffix[3:]  # 去掉开头的 /v1（保留后续的 /）

    return base + suffix


# ============================================================
# API 操作
# ============================================================

def fetch_remote_models(base_url: str, api_key: str):
    """
    从 API 获取远程模型列表。
    返回 (模型ID列表, 状态描述)
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for path, desc in [("/v1/models", "标准端点"), ("/openai/v1/models", "代理端点")]:
        url = _join_url(base_url, path)
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", [])]
                return models, f"通过 {desc} 获取到 {len(models)} 个"
            elif r.status_code == 401:
                return [], "API Key 无效 (401)"
            elif r.status_code == 404:
                continue
            else:
                continue
        except requests.exceptions.RequestException:
            continue
    return [], "该提供商不支持模型列表查询"


def test_model(base_url: str, api_key: str, model_id: str, api_type: str = "openai-completions") -> tuple:
    """
    测试模型是否可用。
    返回 (是否成功, 状态描述)
    """
    api_type = _normalize_api_type(api_type)
    headers = {"Content-Type": "application/json"}

    if api_type == "anthropic-messages":
        headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        url = _join_url(base_url, "/v1/messages")
        body = {"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
    else:
        headers["Authorization"] = f"Bearer {api_key}"
        url = _join_url(base_url, "/v1/chat/completions")
        body = {"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}

    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        if r.status_code == 200:
            return True, f"模型 '{model_id}' 可用 (200)"
        elif r.status_code == 401:
            return False, "API Key 无效 (401)"
        elif r.status_code == 400:
            try:
                err = r.json().get("error", {}).get("message", r.text[:100])
            except Exception:
                err = r.text[:100]
            return False, f"模型不可用 (400): {err}"
        elif r.status_code == 404:
            return False, "端点不存在 (404)，API 类型可能不匹配"
        else:
            detail = (r.text or "")[:160].strip()
            return False, f"请求失败 ({r.status_code}){': ' + detail if detail else ''}"
    except requests.exceptions.RequestException as e:
        return False, f"网络错误: {e}"


# ============================================================
# 操作1: 添加模型
# ============================================================

def action_add(base_url: str, api_key: str, provider_name: str,
               model_id: str, alias: str = "", api_type: str = "openai-completions",
               skip_validation: bool = False) -> bool:
    model_ref = f"{provider_name}/{model_id}"
    if not alias:
        alias = model_id

    api_type = _normalize_api_type(api_type)

    if not skip_validation:
        ok, msg = test_model(base_url, api_key, model_id, api_type)
        if not ok:
            print(f"[验证失败] {msg}")
            return False
        print(f"[验证通过] {msg}")

    # 生成模型条目
    input_types = ["text"]
    if any(kw in model_id.lower() for kw in ["vision", "gpt-4o", "claude-3", "image"]):
        input_types = ["text", "image"]

    new_model = {
        "id": model_id,
        "name": f"{model_id} (Custom Provider)",
        "reasoning": False,
        "input": input_types,
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": 128000,
        "maxTokens": 8192
    }

    cfg = read_config()

    # 确保结构存在
    cfg.setdefault("models", {}).setdefault("providers", {})
    cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {}).setdefault("fallbacks", [])
    cfg["agents"]["defaults"].setdefault("models", {})

    # 写入/更新供应商（同 id 覆盖，避免重复）
    old_provider = cfg["models"]["providers"].get(provider_name, {})
    existing_models = old_provider.get("models", [])
    filtered_models = [m for m in existing_models if m.get("id") != model_id]
    filtered_models.append(new_model)

    merged_provider = dict(old_provider)
    merged_provider.update({
        "baseUrl": base_url,
        "apiKey": api_key,
        "api": api_type,
        "models": filtered_models,
    })
    cfg["models"]["providers"][provider_name] = merged_provider

    # 写入 agents
    fb = cfg["agents"]["defaults"]["model"]["fallbacks"]
    if model_ref not in fb:
        fb.append(model_ref)
    cfg["agents"]["defaults"]["models"][model_ref] = {"alias": alias}

    bak = backup_config()
    if not save_config(cfg):
        return False

    print(f"[成功] 已添加 {provider_name}/{model_id}")
    if bak:
        print(f"[备份] {bak}")
    return True


# ============================================================
# 操作2: 删除模型
# ============================================================

def action_delete(provider_name: str, model_id: str) -> bool:
    cfg = read_config()
    providers = cfg.get("models", {}).get("providers", {})
    model_ref = f"{provider_name}/{model_id}"
    current_default = _get_default_model_from_cfg(cfg)

    if provider_name not in providers:
        print(f"[错误] 供应商 '{provider_name}' 不存在")
        return False

    p_models = providers[provider_name].get("models", [])
    before = len(p_models)
    p_models = [m for m in p_models if m.get("id") != model_id]
    if len(p_models) == before:
        print(f"[错误] 模型 '{model_id}' 不存在于供应商 '{provider_name}'")
        return False

    if p_models:
        cfg["models"]["providers"][provider_name]["models"] = p_models
    else:
        del cfg["models"]["providers"][provider_name]
        print(f"[删除] 供应商 '{provider_name}' 已无模型，一并删除")

    new_default = _clean_default_references(cfg, removed_refs={model_ref})

    bak = backup_config()
    if not save_config(cfg):
        return False

    if current_default == model_ref:
        print(f"[修复] 默认模型已更新为: {new_default or '无'}")
    print(f"[成功] 已删除 {model_ref}")
    if bak:
        print(f"[备份] {bak}")
    return True


def action_delete_provider(provider_name: str) -> bool:
    cfg = read_config()
    providers = cfg.get("models", {}).get("providers", {})
    current_default = _get_default_model_from_cfg(cfg)

    if provider_name not in providers:
        print(f"[错误] 供应商 '{provider_name}' 不存在")
        return False

    provider = providers[provider_name]
    removed_refs = _provider_model_refs(provider_name, provider)
    del cfg["models"]["providers"][provider_name]

    new_default = _clean_default_references(
        cfg,
        removed_refs=removed_refs,
        removed_prefixes={f"{provider_name}/"},
        prefer_first_available=True,
    )

    bak = backup_config()
    if not save_config(cfg):
        return False

    if current_default.startswith(f"{provider_name}/"):
        print(f"[修复] 默认模型已更新为: {new_default or '无'}")
    print(f"[成功] 已删除供应商 '{provider_name}'，共清理 {len(removed_refs)} 个模型引用")
    if bak:
        print(f"[备份] {bak}")
    return True


# ============================================================
# 操作3: 修改供应商密钥
# ============================================================

def action_update_key(provider_name: str, new_base_url: str = "", new_api_key: str = "") -> bool:
    cfg = read_config()
    providers = cfg.get("models", {}).get("providers", {})

    if provider_name not in providers:
        print(f"[错误] 供应商 '{provider_name}' 不存在")
        return False

    if new_base_url:
        cfg["models"]["providers"][provider_name]["baseUrl"] = new_base_url
        print(f"[更新] baseUrl -> {new_base_url}")
    if new_api_key:
        cfg["models"]["providers"][provider_name]["apiKey"] = new_api_key
        print(f"[更新] apiKey 已更新")

    bak = backup_config()
    if not save_config(cfg):
        return False

    if bak:
        print(f"[备份] {bak}")
    return True


# ============================================================
# 主入口
# ============================================================

def main():
    # 优先从 PARAMS JSON 读取（结构化参数）
    params_raw = os.environ.get("PARAMS", "").strip()
    if params_raw:
        try:
            params = json.loads(params_raw)
        except Exception:
            params = {}
    else:
        # 兼容旧方式：直接从环境变量读取
        params = {
            "action": os.environ.get("ACTION", "").strip().lower(),
            "provider": os.environ.get("PROVIDER_NAME", "").strip(),
            "base_url": os.environ.get("BASE_URL", "").strip(),
            "api_key": os.environ.get("API_KEY", "").strip(),
            "model": os.environ.get("MODEL_ID", "").strip(),
            "alias": os.environ.get("ALIAS", "").strip(),
            "api_type": os.environ.get("API_TYPE", "openai-completions").lower(),
            "skip_validation": os.environ.get("SKIP_VALIDATION", "").strip().lower() in ("1", "true", "yes"),
        }

    action = params.get("action", "").lower()
    provider = params.get("provider", "").strip()
    base_url = params.get("base_url", "").strip()
    api_key = params.get("api_key", "").strip()
    model = params.get("model", "").strip()
    alias = params.get("alias", "").strip()
    api_type = _normalize_api_type(params.get("api_type", "openai-completions"))
    skip_validation = bool(params.get("skip_validation", False))

    if action in ("delete-provider", "delete_provider", "remove_provider"):
        action = "delete_provider"
    elif action == "remove":
        action = "delete"


    # ---- 通用：配置可读性检查 ----
    if _is_config_invalid(read_config()):
        print("[错误] 当前配置文件无法解析，请先修复 ~/.openclaw/openclaw.json 后再执行")
        return

    # ---- 通用：缺失 PROVIDER ----
    if not provider:
        print("=== MISSING_INFO ===")
        print("缺少参数: PROVIDER_NAME")
        providers = list_providers()
        if providers:
            print(f"已配置的供应商: {', '.join(providers)}")
        print("请提供: PROVIDER_NAME = 供应商名称")
        return

    # ---- 获取供应商信息 ----
    cached = get_provider_info(provider)
    if cached:
        cfg_base_url = cached.get("baseUrl", "")
        cfg_api_key = cached.get("apiKey", "")
        cfg_api_type = cached.get("api", "openai-completions")

    # ---- 删除操作 ----
    if action == "delete_provider":
        action_delete_provider(provider)
        return

    if action == "delete":
        if not model:
            # 供应商级删除需要单独走 delete_provider
            print("=== MISSING_INFO ===")
            print(f"缺少参数: MODEL_ID")
            models = get_provider_models(provider)
            if models:
                print(f"供应商 '{provider}' 下的模型:")
                default = get_default_model()
                for m in models:
                    mid = m.get("id", "")
                    tag = " (默认)" if f"{provider}/{mid}" == default else ""
                    print(f"  - {mid}{tag}")
                print("如需删除整个供应商，请使用 ACTION=delete_provider")
            else:
                print(f"供应商 '{provider}' 下无模型")
                print("如需删除整个供应商，请使用 ACTION=delete_provider")
            print("请提供: MODEL_ID = 要删除的模型名称")
            return
        action_delete(provider, model)
        return

    # ---- 修改密钥操作 ----
    if action == "update_key":
        new_url = params.get("new_base_url", "").strip()
        new_key = params.get("new_api_key", "").strip()
        if not new_url and not new_key:
            print("=== MISSING_INFO ===")
            print(f"请提供要更新的内容:")
            print(f"  new_base_url = 新的 API 地址（可选）")
            print(f"  new_api_key = 新的 API 密钥（可选）")
            return
        if not cached:
            print(f"[错误] 供应商 '{provider}' 未配置")
            return
        action_update_key(provider, new_url, new_key)
        return

    # ---- 列表操作 ----
    if action == "list":
        if not cached:
            print(f"[错误] 供应商 '{provider}' 未配置，请先添加")
            return
        print(f"[操作] 获取 {provider} 的模型列表...")
        models, desc = fetch_remote_models(cfg_base_url, cfg_api_key)
        if models:
            print(f"[成功] {desc}")
            for m in models:
                print(f"  - {m}")
        else:
            print(f"[失败] {desc}")
        return

    # ---- 测试操作 ----
    if action == "test":
        if not cached:
            print(f"[错误] 供应商 '{provider}' 未配置，请先添加")
            return
        if not model:
            # 自动取列表第一个
            print(f"[信息] 未指定模型，获取列表...")
            models, desc = fetch_remote_models(cfg_base_url, cfg_api_key)
            if models:
                model = models[0]
                print(f"[信息] 使用第一个模型: {model}")
            else:
                print("[错误] 无法获取模型列表，请手动指定 MODEL_ID")
                return
        print(f"[操作] 测试 {provider}/{model}...")
        ok, msg = test_model(cfg_base_url, cfg_api_key, model, cfg_api_type)
        print(f"[{'成功' if ok else '失败'}] {msg}")
        return

    # ---- 添加操作 ----
    if action == "add":
        # 收集缺失信息
        missing = []

        if not base_url:
            missing.append("BASE_URL = API 地址（如 https://api.longcat.chat/openai）")
        if not api_key:
            missing.append("API_KEY = API 密钥")
        if not model:
            missing.append("MODEL_ID = 模型 ID")

        if missing:
            print("=== MISSING_INFO ===")
            print(f"添加供应商 '{provider}' 的模型，缺少以下信息:")
            for m in missing:
                print(f"  - {m}")
            return

        # 可选：自动获取远程模型列表（如果 MODEL_ID 是部分名称需要提示选择）
        # 这里简化处理，直接使用用户提供的 model_id
        action_add(base_url, api_key, provider, model, alias, api_type, skip_validation)
        return

    # ---- 无指定操作 ----
    print("=== MISSING_INFO ===")
    print("缺少参数: ACTION")
    print("支持的 ACTION 值:")
    print("  add            - 添加模型")
    print("  delete         - 删除模型")
    print("  delete_provider - 删除供应商及其全部模型")
    print("  list           - 获取模型列表")
    print("  test           - 测试模型可用性")
    print("  update_key     - 修改供应商密钥")


if __name__ == "__main__":
    main()

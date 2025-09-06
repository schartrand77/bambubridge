import pytest

@pytest.mark.asyncio
async def test_invoke_print_accepts_url_kw(api_module):
    """Function expects ``url`` keyword."""
    def impl(*, url, thmf_url=None):
        return {"url": url, "thmf_url": thmf_url}

    res = await api_module._invoke_print(impl, "http://g", "http://t")
    assert res["url"] == "http://g"
    assert res["thmf_url"] == "http://t"


@pytest.mark.asyncio
async def test_invoke_print_accepts_positional(api_module):
    """Function expects positional arguments."""
    def impl(url, thmf_url=None):
        return {"url": url, "thmf_url": thmf_url}

    res = await api_module._invoke_print(impl, "http://g", "http://t")
    assert res["url"] == "http://g"
    assert res["thmf_url"] == "http://t"


@pytest.mark.asyncio
async def test_invoke_print_async(api_module):
    """Asynchronous function expecting ``url`` keyword."""
    async def impl(*, url, thmf_url=None):
        return {"url": url, "thmf_url": thmf_url}

    res = await api_module._invoke_print(impl, "http://g", None)
    assert res["url"] == "http://g"
    assert res["thmf_url"] is None


@pytest.mark.asyncio
async def test_invoke_print_no_match(api_module):
    """Unsupported function signatures raise ``TypeError``."""
    def impl(a, b):
        return {}

    with pytest.raises(TypeError):
        await api_module._invoke_print(impl, "http://g", None)

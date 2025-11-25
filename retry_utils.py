import asyncio
import logging
from typing import Callable, Any, TypeVar, Optional
from telegram import error as tg_error

logger = logging.getLogger(__name__)

T = TypeVar('T')

DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1.0  # 初始延迟（秒）
DEFAULT_MAX_DELAY = 60.0  # 最大延迟（秒）
DEFAULT_BACKOFF_FACTOR = 2.0  # 指数退避因子


def is_retryable_error(exception: Exception) -> bool:
    if isinstance(exception, (tg_error.NetworkError, tg_error.TimedOut)):
        return True
    
    if isinstance(exception, tg_error.TelegramServerError):
        return True
    
    if isinstance(exception, tg_error.RetryAfter):
        return True
    
    if isinstance(exception, (ConnectionError, OSError)):
        return True
    
    if isinstance(exception, tg_error.TelegramError):
        return False
    
    return True


async def retry_telegram_api(
    func: Callable[..., Any],
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    **kwargs
) -> Any:
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if not is_retryable_error(e):
                logger.error(f"遇到不可重试的错误: {type(e).__name__}: {e}")
                raise
            
            if attempt >= max_retries:
                logger.error(f"达到最大重试次数 ({max_retries})，放弃重试。最后错误: {type(e).__name__}: {e}")
                raise
            
            if isinstance(e, tg_error.RetryAfter):
                delay = float(e.retry_after)
                logger.warning(f"遇到限流错误，等待 {delay} 秒后重试 (尝试 {attempt + 1}/{max_retries})")
            else:
                delay = min(initial_delay * (backoff_factor ** attempt), max_delay)
                logger.warning(
                    f"Telegram API 调用失败 ({type(e).__name__}: {e})，"
                    f"{delay:.2f} 秒后重试 (尝试 {attempt + 1}/{max_retries})"
                )
            
            await asyncio.sleep(delay)
    
    if last_exception:
        raise last_exception


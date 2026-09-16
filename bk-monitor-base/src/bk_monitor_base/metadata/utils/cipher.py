from bk_monitor_base.infras.cipher import AESCipher
from bk_monitor_base.metadata.config import settings


def transform_data_id_to_token(
    metric_data_id: int = -1, trace_data_id: int = -1, log_data_id: int = -1, bk_biz_id: int = -1, app_name: str = ""
) -> str:
    """
    将dataid 加密为bk.data.token
    bk.data.token=${metric_data_id}${salt}${trace_data_id}${salt}${log_data_id}${salt}${bk_biz_id}
    """
    bk_data_token_raw = settings.metadata.bk_data_token_salt.join(
        [
            str(x)
            for x in [
                metric_data_id,
                trace_data_id,
                log_data_id,
                bk_biz_id,
                app_name,
            ]
        ]
    )
    # 需要判断是否有指定密钥，如有，优先级最高
    x_key = settings.metadata.specify_aes_key or settings.blueking.app_secret
    return (
        AESCipher(x_key, settings.metadata.bk_data_aes_iv.encode(encoding="utf-8"))
        .encrypt(bk_data_token_raw)
        .decode("utf-8")
    )

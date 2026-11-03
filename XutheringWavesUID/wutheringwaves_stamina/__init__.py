from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.at_help import ruser_id
from ..utils.util import with_refresh_alias
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_102
from .draw_waves_stamina import draw_stamina_img
from ..utils.database.models import WavesBind, WavesStaminaRecord

waves_daily_info = SV("waves查询体力")


@waves_daily_info.on_fullmatch(
    with_refresh_alias((
        "每日",
        "mr",
        "实时便笺",
        "便笺",
        "便签",
        "体力",
    )),
    to_ai="""查询用户当前鸣潮账号的体力 / 每日实时便笺 / 任务进度。

当用户问「我体力多少 / 现在还有多少结晶波片 / 每日做完了吗 / 看下便笺」时调用。
需要用户已绑定 UID 和 cookie，否则返回未绑定提示。
返回结果是一张图片，包含体力数值、恢复时间、每日任务进度等。

Args:
    text: 无需参数，留空即可。
""",
)
async def send_daily_info_pic(bot: Bot, ev: Event):
    await bot.logger.info(f"[鸣潮·体力] 开始执行[每日信息]: {ruser_id(ev)}")
    uid = await WavesBind.get_uid_by_game(ruser_id(ev), ev.bot_id)
    if not uid:
        # 强需要登录的功能, uid 缺失直接报 102 (登录提示), 避免用户绑定 uid 后再被告知"还要登录"
        return await bot.send(ERROR_CODE[WAVES_CODE_102])
    return await bot.send(await draw_stamina_img(bot, ev))

waves_crazy_notice = SV("waves催命模式")


@waves_crazy_notice.on_fullmatch(("开启催命", "打开催命", "开启体力催命"))
async def open_crazy_notice(bot: Bot, ev: Event):
    await bot.logger.info(f"[鸣潮·催命] 开启催命: {ruser_id(ev)}")
    uid = await WavesBind.get_uid_by_game(ruser_id(ev), ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_102])

    record = await WavesStaminaRecord.get_push_data(uid=uid, bot_id=ev.bot_id)
    if record is None:
        return await bot.send("❌ 未找到体力推送记录，请先使用「每日」初始化后再开启催命")

    await WavesStaminaRecord.update_data_by_uid(
        uid=uid, bot_id=ev.bot_id, stamina_is_push="on"
    )
    return await bot.send(
        "✅ 已开启催命模式\n"
        "体力达到阈值后会按配置的间隔反复提醒\n"
        "发送「关闭催命」可关闭"
    )


@waves_crazy_notice.on_fullmatch(("关闭催命", "关掉催命", "关闭体力催命"))
async def close_crazy_notice(bot: Bot, ev: Event):
    await bot.logger.info(f"[鸣潮·催命] 关闭催命: {ruser_id(ev)}")
    uid = await WavesBind.get_uid_by_game(ruser_id(ev), ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_102])

    record = await WavesStaminaRecord.get_push_data(uid=uid, bot_id=ev.bot_id)
    if record is None:
        return await bot.send("❌ 未找到体力推送记录")

    await WavesStaminaRecord.update_data_by_uid(
        uid=uid, bot_id=ev.bot_id, stamina_is_push="off"
    )
    return await bot.send("❌ 已关闭催命模式")
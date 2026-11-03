from datetime import datetime
import time

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment

from ..utils.api.kuro_py_api import get_base_info_overseas
from ..utils.api.model import DailyData
from ..utils.database.models import WavesStaminaRecord, WavesUser
from ..utils.waves_api import waves_api
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig


async def get_notice_list() -> dict[str, dict[str, dict]]:
    """获取推送列表"""
    if not WutheringWavesConfig.get_config("StaminaPush").data:
        return {}

    msg_dict = {"private_msg_dict": {}, "group_msg_dict": {}}

    user_list = await WavesUser.get_waves_all_user()
    logger.debug(f"[鸣潮] 推送列表: {user_list}")
    for user in user_list:
        if not user.uid or not user.cookie or user.status or not user.bot_id:
            continue

        push_data = await WavesStaminaRecord.get_push_data(user.uid, user.bot_id)
        if push_data is None:
            continue
        if not push_data.stamina_push_time:
            continue
        if push_data.stamina_push_switch == "off":
            continue

        await all_check(push_data, msg_dict, user)

    return msg_dict


async def all_check(push_data: WavesStaminaRecord, msg_dict: dict, user: WavesUser):
    bot_id = user.bot_id
    uid = user.uid

    time_now = int(time.time())
    dt = datetime.strptime(push_data.stamina_push_time, "%Y-%m-%d %H:%M:%S")
    timestamp = int(dt.timestamp())

    _push = await check(time_now, timestamp)
    logger.debug(f"用户{uid} 体力提醒是否应推送:{_push}，开启状态：{push_data.stamina_push_switch}")

    # 催命模式
    if push_data.stamina_is_push == "on":
        if WutheringWavesConfig.get_config("CrazyNotice").data:
            await WavesStaminaRecord.update_data_by_uid(
                uid=uid, bot_id=bot_id, stamina_is_push="off"
            )
            if _push:
                refreshTimeStamp = await get_next_refresh_time(user)
                threshold = push_data.stamina_threshold or 240
                if refreshTimeStamp:
                    time_refresh = int(refreshTimeStamp - (240 - threshold) * 6 * 60)
                else:
                    time_refresh = timestamp

                extended_time = WutheringWavesConfig.get_config("StaminaRemindInterval").data
                time_repush = timestamp + int(extended_time) * 60

                _push = await check(time_repush, time_refresh)

                time_out = time_repush if _push else time_refresh
                time_push = datetime.fromtimestamp(time_out)
                await WavesStaminaRecord.update_data_by_uid(
                    uid=uid, bot_id=bot_id, stamina_push_time=str(time_push)
                )
                logger.info(f"催命模式设置成功!\n当前用户{uid} 体力提醒下一次推送时间:{time_push}\n")
        return

    # 正常推送
    if _push:
        if push_data.stamina_push_switch == "off":
            pass
        else:
            notice = f"🌜您的结晶波片达到设定阈值啦(UID:{uid})！"
            msg_list = [
                MessageSegment.text("✅[鸣潮] 推送提醒:\n"),
                MessageSegment.text(notice),
                MessageSegment.text(f"\n🕒当前体力阈值：{push_data.stamina_threshold}！\n"),
                MessageSegment.text(f"\n📅请清完体力后使用[{PREFIX}每日]来更新推送时间！\n"),
            ]
            await save_push_data(msg_list, push_data, msg_dict, user, True)


async def check(time: int, limit: int) -> bool:
    return time >= limit


async def get_next_refresh_time(user: WavesUser) -> int:
    """获取下次体力刷新时间戳"""
    if not waves_api.is_net(user.uid):
        daily_info_res = await waves_api.get_daily_info(user.uid, user.cookie)
        if daily_info_res.success:
            daily_info = DailyData.model_validate(daily_info_res.data)
            return daily_info.energyData.refreshTimeStamp
    else:
        _, daily_info = await get_base_info_overseas(user.bot_id, user.user_id, user.uid)
        if daily_info:
            return daily_info.energyData.refreshTimeStamp
    return 0


async def save_push_data(msg_list: list, push_data: WavesStaminaRecord, msg_dict: dict, user: WavesUser, is_need_save: bool = False):
    bot_id = user.bot_id
    qid = user.user_id
    uid = user.uid

    private_msgs = msg_dict["private_msg_dict"]
    group_data = msg_dict["group_msg_dict"]

    if push_data.stamina_push_switch == "on":
        if qid not in private_msgs:
            private_msgs[qid] = []
        private_msgs[qid].append({"bot_id": bot_id, "messages": msg_list})
    else:
        gid = push_data.stamina_push_switch
        if gid not in group_data:
            group_data[gid] = []
        msg_list.append(MessageSegment.at(qid))
        group_data[gid].append({"bot_id": bot_id, "messages": msg_list})

    if is_need_save:
        await WavesStaminaRecord.update_data_by_uid(
            uid=uid, bot_id=bot_id, stamina_is_push="on"
        )
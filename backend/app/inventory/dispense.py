"""抽象出货接口。

目标书柜出货机制尚未最终确定（机械货道售卖式 vs RFID 电子门自助式，见 PRD §13.1）。
这里用统一抽象接口隔离差异，业务层只调用 dispense()/confirm_taken()，
待确定具体型号后只需实现/替换适配器，不影响上层。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DispenseResult:
    ok: bool
    mechanism: str
    message: str = ""
    pickup_code: str = ""        # 自取码（电子门/自取场景）
    requires_user_action: bool = False  # 是否需要用户开门/取书后再确认


class Dispenser(ABC):
    """出货适配器抽象基类。"""

    mechanism: str = "abstract"

    @abstractmethod
    def dispense(self, machine_id: str, slot_code: str, rfid_tag: str = "") -> DispenseResult:
        """触发出货/解锁。"""

    def confirm_taken(self, machine_id: str, slot_code: str, rfid_tag: str = "") -> bool:
        """确认用户已取走（RFID/重力感应回执）。默认认为出货即完成。"""
        return True


class VendChannelDispenser(Dispenser):
    """机械货道售卖式：按货道电机出货。"""

    mechanism = "vend_channel"

    def dispense(self, machine_id: str, slot_code: str, rfid_tag: str = "") -> DispenseResult:
        # TODO: 对接具体书柜的货道控制 SDK / 串口协议
        logger.info("[vend] 设备 %s 货道 %s 出货", machine_id, slot_code)
        return DispenseResult(ok=True, mechanism=self.mechanism, message=f"货道 {slot_code} 已出货")


class RFIDDoorDispenser(Dispenser):
    """RFID 电子门自助式：解锁玻璃门，用户取书，RFID 回执核验取走的书。"""

    mechanism = "rfid_door"

    def dispense(self, machine_id: str, slot_code: str, rfid_tag: str = "") -> DispenseResult:
        # TODO: 对接电子锁解锁 + RFID 读写器
        logger.info("[rfid] 设备 %s 解锁，待取 RFID=%s", machine_id, rfid_tag)
        return DispenseResult(
            ok=True, mechanism=self.mechanism, message="已解锁，请取书后关门",
            requires_user_action=True,
        )

    def confirm_taken(self, machine_id: str, slot_code: str, rfid_tag: str = "") -> bool:
        # TODO: 读 RFID 出门事件，核对是否取走目标标签
        logger.info("[rfid] 设备 %s 核对取走 RFID=%s", machine_id, rfid_tag)
        return True


class SimulatedDispenser(Dispenser):
    """开发/测试用：不连硬件，永远成功。"""

    mechanism = "simulated"

    def dispense(self, machine_id: str, slot_code: str, rfid_tag: str = "") -> DispenseResult:
        return DispenseResult(ok=True, mechanism=self.mechanism, message="模拟出货成功")


_REGISTRY: dict[str, type[Dispenser]] = {
    VendChannelDispenser.mechanism: VendChannelDispenser,
    RFIDDoorDispenser.mechanism: RFIDDoorDispenser,
    SimulatedDispenser.mechanism: SimulatedDispenser,
}


def get_dispenser(mechanism: str = "simulated") -> Dispenser:
    cls = _REGISTRY.get(mechanism, SimulatedDispenser)
    return cls()

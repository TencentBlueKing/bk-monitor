from typing import ClassVar

from django.core.management import BaseCommand

from bk_monitor_base.infras.declaratives.controller.base_controller import BaseController
from bk_monitor_base.infras.declaratives.logger import logger


class BaseControllerCommand(BaseCommand):
    controller: ClassVar[BaseController]

    def handle(self, *args, **options):
        try:
            self.controller.start()
        except KeyboardInterrupt:
            logger.info("Controller stopped by user")
            print("Controller stopped by user")

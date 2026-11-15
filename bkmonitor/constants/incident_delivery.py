from django.db.models import TextChoices

from constants.action import NoticeWay


class IncidentNoticeDeliveryStatus(TextChoices):
    PENDING = "pending", "Pending"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    UNCERTAIN = "uncertain", "Uncertain"


DELIVERY_UNCERTAIN_AFTER_SECONDS = 600

# These legacy senders also return False on transport exceptions.
AMBIGUOUS_FAILURE_NOTICE_WAYS = {NoticeWay.VOICE, NoticeWay.WX_BOT}

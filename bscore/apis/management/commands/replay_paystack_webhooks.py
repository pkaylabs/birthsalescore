from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apis.models import PaystackWebhookEvent, Payment
from bscore.utils.const import PaymentStatus, PaymentStatusCode
from bscore.utils.services import finalize_paystack_payment


class Command(BaseCommand):
    help = "Replay queued Paystack webhook events where local Payment was missing at receive time."

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200, help='Max events to process')
        parser.add_argument('--max-attempts', type=int, default=10, help='Skip events with attempts >= max')

    def handle(self, *args, **options):
        limit = int(options['limit'])
        max_attempts = int(options['max_attempts'])

        qs = (
            PaystackWebhookEvent.objects
            .filter(processed=False, attempts__lt=max_attempts)
            .order_by('created_at')
        )
        events = list(qs[:limit])

        if not events:
            self.stdout.write(self.style.SUCCESS('No queued Paystack webhook events to replay.'))
            return

        processed = 0
        skipped_missing_payment = 0
        failed = 0

        for evt in events:
            reference = str(evt.reference)

            # Only replay once a local Payment exists; otherwise keep it queued.
            if not Payment.objects.filter(payment_id=reference).exists():
                with transaction.atomic():
                    PaystackWebhookEvent.objects.filter(id=evt.id).update(attempts=evt.attempts + 1, last_error='Payment still missing')
                skipped_missing_payment += 1
                continue

            try:
                result = finalize_paystack_payment(reference)
            except Exception as e:
                with transaction.atomic():
                    PaystackWebhookEvent.objects.filter(id=evt.id).update(attempts=evt.attempts + 1, last_error=str(e))
                failed += 1
                continue

            status_text = result.get('status')

            # Mark as processed when local Payment has reached a terminal state (SUCCESS/FAILED).
            payment = Payment.objects.filter(payment_id=reference).first()
            is_success = False
            is_failed = False
            if payment:
                is_success = (
                    payment.status == PaymentStatus.SUCCESS.value
                    and payment.status_code == PaymentStatusCode.SUCCESS.value
                )
                is_failed = (
                    payment.status == PaymentStatus.FAILED.value
                    and payment.status_code == PaymentStatusCode.FAILED.value
                )

            if status_text == PaymentStatus.SUCCESS.value or is_success:
                with transaction.atomic():
                    PaystackWebhookEvent.objects.filter(id=evt.id).update(
                        processed=True,
                        processed_at=timezone.now(),
                        attempts=evt.attempts + 1,
                        last_error=None,
                    )
                processed += 1
            elif status_text == PaymentStatus.FAILED.value or is_failed:
                with transaction.atomic():
                    PaystackWebhookEvent.objects.filter(id=evt.id).update(
                        processed=True,
                        processed_at=timezone.now(),
                        attempts=evt.attempts + 1,
                        last_error='Terminal FAILED reconciliation',
                    )
                processed += 1
            else:
                with transaction.atomic():
                    PaystackWebhookEvent.objects.filter(id=evt.id).update(attempts=evt.attempts + 1, last_error=f"Not successful yet: {status_text}")
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f"Replay done. processed={processed}, skipped_missing_payment={skipped_missing_payment}, failed={failed}"
        ))

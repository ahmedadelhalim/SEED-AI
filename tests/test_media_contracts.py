from unittest import TestCase

from interfaces.media import (
    AssistantState,
    AvatarPresentationAdapter,
    SpeechInputAdapter,
    SpeechOutputAdapter,
    SpeechRequest,
    SpeechTranscript,
    VisualStateClient,
    VisualStateUpdate,
    WakeWordPolicy,
)


class MediaContractTests(TestCase):
    def test_wake_word_is_off_by_default_and_requires_privacy_acknowledgement(self):
        self.assertFalse(WakeWordPolicy().enabled)
        with self.assertRaises(PermissionError):
            WakeWordPolicy(enabled=True)
        self.assertTrue(WakeWordPolicy(
            enabled=True, privacy_acknowledged=True
        ).enabled)

    def test_speech_contracts_accept_arabic_and_english_only(self):
        self.assertEqual(SpeechTranscript("مرحبا", "ar").language, "ar")
        self.assertEqual(
            SpeechRequest("Hello", "en", "session-1").session_id,
            "session-1",
        )
        with self.assertRaises(ValueError):
            SpeechTranscript("bonjour", "fr")
        with self.assertRaises(ValueError):
            SpeechTranscript("hello", "en", confidence=1.5)

    def test_visual_state_contract_carries_seed_state_not_decisions(self):
        update = VisualStateUpdate(
            AssistantState.AWAITING_APPROVAL,
            "session-2",
            task_id=4,
            event_id=12,
        )

        self.assertEqual(update.state.value, "awaiting_approval")
        self.assertEqual(update.task_id, 4)

    def test_media_adapters_are_replaceable_interfaces_not_live_features(self):
        for adapter in (SpeechInputAdapter, SpeechOutputAdapter,
                        VisualStateClient, AvatarPresentationAdapter):
            with self.subTest(adapter=adapter.__name__):
                with self.assertRaises(TypeError):
                    adapter()


if __name__ == "__main__":
    import unittest

    unittest.main()
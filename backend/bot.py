import asyncio
import sys

import aiohttp
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame, TextFrame, LLMFullResponseEndFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

import config
from prompts import BUBBLES_GREETING, BUBBLES_SYSTEM_PROMPT

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


class TextToTransport(FrameProcessor):
    """Captures LLM text and sends it to the client as app messages."""

    def __init__(self, transport, **kwargs):
        super().__init__(**kwargs)
        self._transport = transport
        self._buffer = ""

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            self._buffer += frame.text
            # Send streaming text to client
            await self._transport.send_app_message({"text": self._buffer})
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._buffer = ""

        await self.push_frame(frame, direction)


async def run_bot(room_url: str, token: str):
    async with aiohttp.ClientSession() as session:
        transport = DailyTransport(
            room_url,
            token,
            "Bubbles",
            DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                transcription_enabled=True,
                transcription_settings={
                    "language": "en",
                    "model": "nova-2-general",
                    "profanity_filter": True,
                    "punctuate": True,
                },
            ),
        )

        llm = OpenAILLMService(
            api_key=config.MINIMAX_API_KEY,
            base_url="https://api.minimax.io/v1",
            settings=OpenAILLMService.Settings(
                model="MiniMax-M2.5",
                system_instruction=BUBBLES_SYSTEM_PROMPT,
                max_tokens=150,
                temperature=0.8,
            ),
        )

        text_sender = TextToTransport(transport)

        context = LLMContext()
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(),
            ),
        )

        pipeline = Pipeline(
            [
                transport.input(),
                user_aggregator,
                llm,
                text_sender,
                transport.output(),
                assistant_aggregator,
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            await transport.capture_participant_transcription(participant["id"])
            context.add_message({"role": "user", "content": BUBBLES_GREETING})
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            logger.info(f"Participant left: {reason}")
            await task.cancel()

        runner = PipelineRunner()
        logger.info(f"Bot starting in room: {room_url}")
        await runner.run(task)
        logger.info("Bot finished")

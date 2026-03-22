import asyncio
import sys

import aiohttp
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.minimax.tts import MiniMaxHttpTTSService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

import config
from prompts import BUBBLES_GREETING, BUBBLES_SYSTEM_PROMPT

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


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

        tts = MiniMaxHttpTTSService(
            api_key=config.MINIMAX_API_KEY,
            group_id=config.MINIMAX_GROUP_ID,
            aiohttp_session=session,
            settings=MiniMaxHttpTTSService.Settings(
                voice="Calm_Woman",
                model="speech-02-hd",
                speed=1.05,
                emotion="happy",
            ),
        )

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
                tts,
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

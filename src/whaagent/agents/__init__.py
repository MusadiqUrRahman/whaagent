from .br_news import BrNewsAgent
from .committer import CommitterAgent
from .developer import DeveloperAgent
from .es_news import EsNewsAgent
from .github_pr_reviewer import GithubPrReviewerAgent
from .learning import LearningAgent
from .news import NewsAgent
from .ollama import OllamaAgent
from .paywall_remover import PaywallRemoverAgent
from .recipe import RecipeAgent
from .youtube import YouTubeAgent

__all__ = [
    "BrNewsAgent",
    "CommitterAgent",
    "DeveloperAgent",
    "EsNewsAgent",
    "GithubPrReviewerAgent",
    "LearningAgent",
    "NewsAgent",
    "OllamaAgent",
    "PaywallRemoverAgent",
    "RecipeAgent",
    "YouTubeAgent",
]

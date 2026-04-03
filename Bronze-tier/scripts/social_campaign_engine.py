#!/usr/bin/env python3
"""
Social Campaign Engine
======================

Gold Tier Strategic Layer - AI-Powered Campaign & Strategic Planning Engine

This is the system's STRATEGIC BRAIN. It reads business goals, generates
7-day multi-platform campaign plans, adapts tone per platform, and outputs
drafts for the approval workflow.

Usage:
    python3 scripts/social_campaign_engine.py
    python3 scripts/social_campaign_engine.py --week
    python3 scripts/social_campaign_engine.py --verbose

Exit Codes:
    0 - Success
    1 - Missing goals file
    2 - Generation failure

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import json
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import get_audit_logger, ActionType, ResultStatus


# ==============================================================================
# EXIT CODES
# ==============================================================================

class ExitCode:
    SUCCESS = 0
    MISSING_GOALS = 1
    GENERATION_FAILURE = 2


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Config:
    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"

    # Input paths
    BUSINESS_GOALS_FILE = VAULT_DIR / "Business" / "business_goals.json"
    ANALYTICS_FILE = VAULT_DIR / "Analytics" / "social_metrics.json"

    # Output paths
    DRAFTS_DIR = VAULT_DIR / "Drafts"
    EXECUTIVE_DIR = VAULT_DIR / "Executive"

    # Constraints
    MIN_POST_LENGTH = 50
    TWITTER_MAX_LENGTH = 280
    INSTAGRAM_MAX_LENGTH = 2200
    FACEBOOK_MAX_LENGTH = 5000
    LINKEDIN_MAX_LENGTH = 3000

    # Actor
    ACTOR = "social_campaign_engine"


# ==============================================================================
# PLATFORM DEFINITIONS
# ==============================================================================

class Platform(Enum):
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"


@dataclass
class PlatformProfile:
    """Platform-specific content guidelines."""
    name: str
    prefix: str
    max_length: int
    tone_modifier: str
    hashtag_count: Tuple[int, int]  # min, max
    best_times: List[str]
    content_style: str
    emoji_level: str  # none, minimal, moderate, heavy


PLATFORM_PROFILES: Dict[Platform, PlatformProfile] = {
    Platform.FACEBOOK: PlatformProfile(
        name="Facebook",
        prefix="FACEBOOK_POST",
        max_length=Config.FACEBOOK_MAX_LENGTH,
        tone_modifier="conversational and engaging with storytelling elements",
        hashtag_count=(3, 5),
        best_times=["09:00", "13:00", "16:00"],
        content_style="longer form with questions to drive engagement",
        emoji_level="moderate"
    ),
    Platform.LINKEDIN: PlatformProfile(
        name="LinkedIn",
        prefix="LINKEDIN_POST",
        max_length=Config.LINKEDIN_MAX_LENGTH,
        tone_modifier="professional, thought-leadership focused",
        hashtag_count=(3, 5),
        best_times=["08:00", "12:00", "17:00"],
        content_style="professional insights with industry relevance",
        emoji_level="minimal"
    ),
    Platform.TWITTER: PlatformProfile(
        name="Twitter",
        prefix="TWITTER_POST",
        max_length=Config.TWITTER_MAX_LENGTH,
        tone_modifier="punchy, concise, and attention-grabbing",
        hashtag_count=(2, 3),
        best_times=["09:00", "12:00", "17:00", "21:00"],
        content_style="short, impactful statements with hooks",
        emoji_level="minimal"
    ),
    Platform.INSTAGRAM: PlatformProfile(
        name="Instagram",
        prefix="INSTAGRAM_POST",
        max_length=Config.INSTAGRAM_MAX_LENGTH,
        tone_modifier="visual-friendly, inspiring, and authentic",
        hashtag_count=(5, 15),
        best_times=["11:00", "14:00", "19:00"],
        content_style="story-driven with call-to-action",
        emoji_level="heavy"
    ),
}


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class BusinessGoals:
    """Business goals configuration."""
    primary_goal: str
    target_audience: str
    tone: str
    weekly_focus: str
    brand_voice: str = "professional"
    key_messages: List[str] = field(default_factory=list)
    avoid_topics: List[str] = field(default_factory=list)
    cta_preference: str = "subtle"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BusinessGoals':
        return cls(
            primary_goal=data.get("primary_goal", "Increase brand awareness"),
            target_audience=data.get("target_audience", "General audience"),
            tone=data.get("tone", "Professional"),
            weekly_focus=data.get("weekly_focus", "Company updates"),
            brand_voice=data.get("brand_voice", "professional"),
            key_messages=data.get("key_messages", []),
            avoid_topics=data.get("avoid_topics", []),
            cta_preference=data.get("cta_preference", "subtle"),
        )


@dataclass
class AnalyticsData:
    """Social media analytics data."""
    top_performing_topics: List[str] = field(default_factory=list)
    best_posting_times: Dict[str, List[str]] = field(default_factory=dict)
    engagement_rates: Dict[str, float] = field(default_factory=dict)
    audience_growth: Dict[str, float] = field(default_factory=dict)
    top_hashtags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalyticsData':
        return cls(
            top_performing_topics=data.get("top_performing_topics", []),
            best_posting_times=data.get("best_posting_times", {}),
            engagement_rates=data.get("engagement_rates", {}),
            audience_growth=data.get("audience_growth", {}),
            top_hashtags=data.get("top_hashtags", []),
        )


@dataclass
class DailyTheme:
    """Theme for a specific day."""
    date: datetime
    day_number: int
    theme: str
    core_message: str
    content_angle: str
    hashtag_suggestions: List[str]
    narrative_hook: str


@dataclass
class PlatformPost:
    """Platform-specific post content."""
    platform: Platform
    content: str
    hashtags: List[str]
    suggested_time: str
    media_suggestion: Optional[str]
    cta: Optional[str]

    @property
    def full_content(self) -> str:
        parts = [self.content]
        if self.hashtags:
            parts.append("")
            parts.append(" ".join(self.hashtags))
        return "\n".join(parts)

    @property
    def content_length(self) -> int:
        return len(self.full_content)


@dataclass
class DailyPlan:
    """Complete plan for a single day."""
    theme: DailyTheme
    posts: Dict[Platform, PlatformPost]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.theme.date.strftime("%Y-%m-%d"),
            "day_number": self.theme.day_number,
            "theme": self.theme.theme,
            "core_message": self.theme.core_message,
            "posts": {
                p.value: {
                    "content": post.content,
                    "hashtags": post.hashtags,
                    "suggested_time": post.suggested_time,
                }
                for p, post in self.posts.items()
            }
        }


@dataclass
class CampaignStrategy:
    """Complete 7-day campaign strategy."""
    start_date: datetime
    end_date: datetime
    goals: BusinessGoals
    weekly_narrative: str
    daily_plans: List[DailyPlan]
    total_posts: int
    platforms_covered: List[str]
    expected_impact: str
    risk_notes: List[str]


# ==============================================================================
# CONTENT GENERATION ENGINE
# ==============================================================================

class ContentGenerator:
    """AI-powered content generation engine."""

    # Theme templates based on common marketing strategies
    THEME_TEMPLATES = [
        ("Problem Awareness", "Highlight challenges your audience faces", "pain point"),
        ("Solution Introduction", "Present your solution to the problem", "solution"),
        ("Social Proof", "Share success stories and testimonials", "credibility"),
        ("Educational Value", "Teach something valuable to your audience", "education"),
        ("Behind the Scenes", "Show the human side of your brand", "authenticity"),
        ("Community Engagement", "Foster discussion and interaction", "engagement"),
        ("Call to Action", "Drive specific action from your audience", "conversion"),
    ]

    # Hook templates
    HOOKS = {
        "question": [
            "Have you ever wondered {}?",
            "What if {} was possible?",
            "Are you struggling with {}?",
            "Ready to transform {}?",
        ],
        "statement": [
            "The future of {} is here.",
            "We're changing how {} works.",
            "It's time to rethink {}.",
            "{} will never be the same.",
        ],
        "statistic": [
            "Did you know that {}?",
            "Studies show that {}.",
            "The data is clear: {}.",
            "{} - and the numbers prove it.",
        ],
    }

    # CTA templates
    CTAS = {
        "subtle": [
            "Learn more in bio.",
            "What do you think?",
            "Share your thoughts below.",
            "Tag someone who needs this.",
        ],
        "moderate": [
            "Click the link to discover more.",
            "Follow for more insights.",
            "Save this for later.",
            "Join the conversation.",
        ],
        "strong": [
            "Sign up now - link in bio!",
            "Don't miss out - act today!",
            "Get started for free!",
            "Limited time - grab it now!",
        ],
    }

    # Hashtag pools by category
    HASHTAG_POOLS = {
        "tech": ["#Tech", "#Innovation", "#Digital", "#Future", "#AI", "#Automation", "#Software"],
        "business": ["#Business", "#Entrepreneur", "#Startup", "#Growth", "#Success", "#Leadership"],
        "marketing": ["#Marketing", "#DigitalMarketing", "#SocialMedia", "#Content", "#Branding"],
        "motivation": ["#Motivation", "#Inspiration", "#Goals", "#Mindset", "#Success"],
        "general": ["#Trending", "#MustSee", "#Explore", "#Discover", "#Community"],
    }

    def __init__(self, goals: BusinessGoals, analytics: Optional[AnalyticsData] = None):
        self.goals = goals
        self.analytics = analytics

    def generate_weekly_narrative(self) -> str:
        """Generate overarching narrative for the week."""
        narratives = [
            f"This week, we're focusing on {self.goals.weekly_focus} to help {self.goals.target_audience} achieve {self.goals.primary_goal}.",
            f"Our mission this week: empowering {self.goals.target_audience} through {self.goals.weekly_focus}.",
            f"Week of transformation: bringing {self.goals.weekly_focus} to {self.goals.target_audience}.",
            f"Strategic focus: {self.goals.primary_goal} through compelling content about {self.goals.weekly_focus}.",
        ]
        return random.choice(narratives)

    def generate_theme_for_day(self, day_number: int, date: datetime) -> DailyTheme:
        """Generate theme for a specific day."""
        theme_name, description, angle = self.THEME_TEMPLATES[day_number - 1]

        # Generate core message based on goals
        core_messages = self._generate_core_messages(theme_name, angle)
        core_message = random.choice(core_messages)

        # Generate hashtags
        hashtags = self._generate_hashtags(theme_name)

        # Generate hook
        hook_type = random.choice(list(self.HOOKS.keys()))
        hook_template = random.choice(self.HOOKS[hook_type])
        hook = hook_template.format(self.goals.weekly_focus.lower())

        return DailyTheme(
            date=date,
            day_number=day_number,
            theme=theme_name,
            core_message=core_message,
            content_angle=angle,
            hashtag_suggestions=hashtags,
            narrative_hook=hook,
        )

    def _generate_core_messages(self, theme: str, angle: str) -> List[str]:
        """Generate core message variants."""
        focus = self.goals.weekly_focus
        audience = self.goals.target_audience
        goal = self.goals.primary_goal

        messages = {
            "pain point": [
                f"{audience} often struggle with inefficiency. Here's how {focus} changes that.",
                f"The biggest challenge for {audience}? We have the answer.",
                f"Stop wasting time. {focus} is the solution {audience} have been waiting for.",
            ],
            "solution": [
                f"Introducing a better way to handle {focus} for {audience}.",
                f"The game-changer {audience} need: {focus} made simple.",
                f"Transform your approach to {focus} starting today.",
            ],
            "credibility": [
                f"See how others are achieving {goal} with our approach.",
                f"Real results from real {audience} using {focus}.",
                f"The proof is in the results: {focus} delivers.",
            ],
            "education": [
                f"Everything {audience} need to know about {focus}.",
                f"Master {focus} with these essential insights.",
                f"Level up your knowledge: {focus} fundamentals.",
            ],
            "authenticity": [
                f"The story behind our mission to help {audience}.",
                f"Why we're passionate about {focus}.",
                f"Meet the team bringing {focus} to {audience}.",
            ],
            "engagement": [
                f"We want to hear from {audience}: what matters most to you?",
                f"Join the conversation about {focus}.",
                f"Your voice matters: share your {focus} experience.",
            ],
            "conversion": [
                f"Ready to transform your approach to {focus}?",
                f"Take the next step toward {goal}.",
                f"The time is now: start your {focus} journey.",
            ],
        }

        return messages.get(angle, messages["solution"])

    def _generate_hashtags(self, theme: str) -> List[str]:
        """Generate relevant hashtags."""
        hashtags = []

        # Add from analytics if available
        if self.analytics and self.analytics.top_hashtags:
            hashtags.extend(self.analytics.top_hashtags[:3])

        # Add category-specific
        categories = ["tech", "business", "general"]
        for cat in categories:
            pool = self.HASHTAG_POOLS.get(cat, [])
            if pool:
                hashtags.extend(random.sample(pool, min(2, len(pool))))

        # Deduplicate and limit
        return list(dict.fromkeys(hashtags))[:10]

    def generate_platform_post(
        self,
        theme: DailyTheme,
        platform: Platform
    ) -> PlatformPost:
        """Generate platform-specific post content."""
        profile = PLATFORM_PROFILES[platform]

        # Generate base content
        content = self._adapt_content_for_platform(theme, profile)

        # Select hashtags
        hashtag_min, hashtag_max = profile.hashtag_count
        hashtag_count = random.randint(hashtag_min, hashtag_max)
        hashtags = [f"#{tag.strip('#')}" for tag in theme.hashtag_suggestions[:hashtag_count]]

        # Select posting time
        suggested_time = random.choice(profile.best_times)

        # Generate CTA
        cta_pool = self.CTAS.get(self.goals.cta_preference, self.CTAS["subtle"])
        cta = random.choice(cta_pool)

        # Media suggestion
        media = self._suggest_media(platform, theme)

        return PlatformPost(
            platform=platform,
            content=content,
            hashtags=hashtags,
            suggested_time=suggested_time,
            media_suggestion=media,
            cta=cta,
        )

    def _adapt_content_for_platform(
        self,
        theme: DailyTheme,
        profile: PlatformProfile
    ) -> str:
        """Adapt content for specific platform."""

        if profile.name == "Twitter":
            return self._generate_twitter_content(theme)
        elif profile.name == "LinkedIn":
            return self._generate_linkedin_content(theme)
        elif profile.name == "Instagram":
            return self._generate_instagram_content(theme)
        elif profile.name == "Facebook":
            return self._generate_facebook_content(theme)

        return theme.core_message

    def _generate_twitter_content(self, theme: DailyTheme) -> str:
        """Generate Twitter-optimized content (max 280 chars)."""
        templates = [
            f"{theme.narrative_hook}\n\n{self.goals.weekly_focus} is transforming how we work.",
            f"Day {theme.day_number}: {theme.theme}\n\n{theme.core_message[:150]}",
            f"{theme.core_message[:200]}\n\nThread below.",
            f"Quick insight: {theme.core_message[:180]}",
        ]

        content = random.choice(templates)

        # Ensure under limit (leaving room for hashtags)
        if len(content) > 220:
            content = content[:217] + "..."

        return content

    def _generate_linkedin_content(self, theme: DailyTheme) -> str:
        """Generate LinkedIn-optimized content."""
        intro_hooks = [
            f"I've been thinking a lot about {self.goals.weekly_focus} lately.",
            f"Here's something most {self.goals.target_audience} don't realize:",
            f"Let me share an insight about {self.goals.weekly_focus}.",
            f"The conversation around {self.goals.weekly_focus} is evolving.",
        ]

        body_templates = [
            f"{theme.core_message}\n\nThis matters because {self.goals.target_audience} deserve better tools and approaches.",
            f"{theme.core_message}\n\nIn my experience, this is where transformation begins.",
            f"{theme.core_message}\n\nThe implications for {self.goals.target_audience} are significant.",
        ]

        closing = [
            f"\n\nWhat's your take on {self.goals.weekly_focus}?",
            f"\n\nI'd love to hear how you're approaching this.",
            f"\n\nAre you seeing similar trends in your work?",
            f"\n\nLet's discuss in the comments.",
        ]

        content = (
            f"{random.choice(intro_hooks)}\n\n"
            f"{random.choice(body_templates)}"
            f"{random.choice(closing)}"
        )

        return content

    def _generate_instagram_content(self, theme: DailyTheme) -> str:
        """Generate Instagram-optimized content."""
        emoji_hooks = ["✨", "🚀", "💡", "🎯", "⚡", "🔥", "💪", "🌟"]

        templates = [
            f"{random.choice(emoji_hooks)} {theme.theme.upper()} {random.choice(emoji_hooks)}\n\n{theme.core_message}\n\n{random.choice(emoji_hooks)} {self.goals.weekly_focus} is changing everything.\n\nDouble tap if you agree! 👇",
            f"Day {theme.day_number} of our {self.goals.weekly_focus} series {random.choice(emoji_hooks)}\n\n{theme.core_message}\n\nSave this for later! 📌",
            f"{theme.narrative_hook} {random.choice(emoji_hooks)}\n\n{theme.core_message}\n\nTag someone who needs to see this! 👥",
        ]

        return random.choice(templates)

    def _generate_facebook_content(self, theme: DailyTheme) -> str:
        """Generate Facebook-optimized content."""
        templates = [
            f"🎯 {theme.theme}\n\n{theme.narrative_hook}\n\n{theme.core_message}\n\nWe're on a mission to help {self.goals.target_audience} achieve {self.goals.primary_goal}.\n\nWhat challenges are you facing with {self.goals.weekly_focus}? Let us know in the comments! 👇",
            f"Day {theme.day_number}: {theme.theme}\n\n{theme.core_message}\n\nThis is part of our ongoing commitment to {self.goals.target_audience}.\n\n💬 We'd love to hear your thoughts - what's your experience with {self.goals.weekly_focus}?",
            f"{theme.narrative_hook}\n\n{theme.core_message}\n\nAt the heart of everything we do is helping {self.goals.target_audience} succeed.\n\n🔔 Follow our page for daily insights on {self.goals.weekly_focus}!",
        ]

        return random.choice(templates)

    def _suggest_media(self, platform: Platform, theme: DailyTheme) -> str:
        """Suggest media type for the post."""
        suggestions = {
            Platform.INSTAGRAM: f"Visual: Branded graphic showcasing '{theme.theme}' concept",
            Platform.FACEBOOK: f"Image or short video related to {theme.theme.lower()}",
            Platform.LINKEDIN: f"Professional infographic or data visualization",
            Platform.TWITTER: f"Eye-catching graphic or meme (optional)",
        }
        return suggestions.get(platform, "Relevant branded image")


# ==============================================================================
# CAMPAIGN ENGINE
# ==============================================================================

class SocialCampaignEngine:
    """Main campaign generation engine."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.audit_logger = get_audit_logger()
        self.goals: Optional[BusinessGoals] = None
        self.analytics: Optional[AnalyticsData] = None
        self.generator: Optional[ContentGenerator] = None

    def _log(self, message: str, level: str = "INFO"):
        """Print timestamped log message."""
        if self.verbose or level in ("ERROR", "WARN"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

    def _audit_log(
        self,
        action: str,
        target: str,
        parameters: Dict[str, Any] = None,
        result: ResultStatus = ResultStatus.SUCCESS,
        error: str = None
    ):
        """Log action to audit system."""
        self.audit_logger.log(
            action_type=ActionType.TASK_STARTED,
            actor=Config.ACTOR,
            target=target,
            parameters={"action": action, **(parameters or {})},
            result=result,
            error=error
        )

    def load_business_goals(self) -> bool:
        """Load business goals from JSON file."""
        self._log(f"Loading business goals from: {Config.BUSINESS_GOALS_FILE}")

        if not Config.BUSINESS_GOALS_FILE.exists():
            self._log(f"Business goals file not found!", "ERROR")
            return False

        try:
            with open(Config.BUSINESS_GOALS_FILE, 'r') as f:
                data = json.load(f)

            self.goals = BusinessGoals.from_dict(data)
            self._log(f"Loaded goals: {self.goals.primary_goal}")
            return True

        except json.JSONDecodeError as e:
            self._log(f"Invalid JSON in goals file: {e}", "ERROR")
            return False
        except Exception as e:
            self._log(f"Error loading goals: {e}", "ERROR")
            return False

    def load_analytics_if_available(self) -> bool:
        """Load analytics data if available."""
        if not Config.ANALYTICS_FILE.exists():
            self._log("Analytics file not found - proceeding without analytics data")
            return False

        try:
            with open(Config.ANALYTICS_FILE, 'r') as f:
                data = json.load(f)

            self.analytics = AnalyticsData.from_dict(data)
            self._log("Loaded analytics data")
            return True

        except Exception as e:
            self._log(f"Error loading analytics: {e}", "WARN")
            return False

    def generate_campaign_strategy(self, start_date: datetime) -> CampaignStrategy:
        """Generate complete 7-day campaign strategy."""
        self._log("Generating campaign strategy...")

        self.generator = ContentGenerator(self.goals, self.analytics)

        # Generate weekly narrative
        weekly_narrative = self.generator.generate_weekly_narrative()
        self._log(f"Weekly narrative: {weekly_narrative[:100]}...")

        # Generate daily plans
        daily_plans = []
        for day in range(1, 8):
            date = start_date + timedelta(days=day - 1)
            plan = self.generate_daily_plan(day, date)
            daily_plans.append(plan)
            self._log(f"Day {day} ({date.strftime('%Y-%m-%d')}): {plan.theme.theme}")

        # Calculate totals
        total_posts = sum(len(plan.posts) for plan in daily_plans)
        platforms = [p.value for p in Platform]

        # Risk notes
        risk_notes = self._assess_risks(daily_plans)

        # Expected impact
        expected_impact = self._estimate_impact()

        strategy = CampaignStrategy(
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            goals=self.goals,
            weekly_narrative=weekly_narrative,
            daily_plans=daily_plans,
            total_posts=total_posts,
            platforms_covered=platforms,
            expected_impact=expected_impact,
            risk_notes=risk_notes,
        )

        self._log(f"Strategy generated: {total_posts} posts across {len(platforms)} platforms")

        return strategy

    def generate_daily_plan(self, day_number: int, date: datetime) -> DailyPlan:
        """Generate complete plan for a single day."""
        # Generate theme
        theme = self.generator.generate_theme_for_day(day_number, date)

        # Generate platform variants
        posts = self.generate_platform_variants(theme)

        return DailyPlan(theme=theme, posts=posts)

    def generate_platform_variants(self, theme: DailyTheme) -> Dict[Platform, PlatformPost]:
        """Generate posts for all platforms."""
        posts = {}

        for platform in Platform:
            post = self.generator.generate_platform_post(theme, platform)

            # Validate minimum length
            if post.content_length >= Config.MIN_POST_LENGTH:
                posts[platform] = post
            else:
                self._log(f"Post for {platform.value} too short, regenerating...", "WARN")
                # Retry once
                post = self.generator.generate_platform_post(theme, platform)
                posts[platform] = post

        return posts

    def _assess_risks(self, daily_plans: List[DailyPlan]) -> List[str]:
        """Assess potential risks in the campaign."""
        risks = []

        # Check content variety
        themes = [plan.theme.theme for plan in daily_plans]
        if len(set(themes)) < 5:
            risks.append("Limited theme variety - consider diversifying content angles")

        # Check for short posts
        short_posts = 0
        for plan in daily_plans:
            for post in plan.posts.values():
                if post.content_length < 100:
                    short_posts += 1

        if short_posts > 5:
            risks.append(f"{short_posts} posts are relatively short - may need enrichment")

        # Check hashtag diversity
        all_hashtags = []
        for plan in daily_plans:
            all_hashtags.extend(plan.theme.hashtag_suggestions)

        if len(set(all_hashtags)) < 10:
            risks.append("Limited hashtag variety - consider expanding hashtag strategy")

        if not risks:
            risks.append("No significant risks identified")

        return risks

    def _estimate_impact(self) -> str:
        """Estimate expected impact of the campaign."""
        impacts = [
            f"Expected to increase visibility among {self.goals.target_audience} by consistent daily posting",
            f"Projected engagement boost through platform-optimized content focused on {self.goals.weekly_focus}",
            f"Brand awareness expansion via multi-platform presence targeting {self.goals.primary_goal}",
        ]
        return random.choice(impacts)

    def save_drafts(self, strategy: CampaignStrategy) -> int:
        """Save all drafts to the Drafts folder."""
        self._log("Saving drafts...")

        # Ensure directory exists
        Config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

        drafts_saved = 0

        for plan in strategy.daily_plans:
            date_str = plan.theme.date.strftime("%Y%m%d")
            topic = plan.theme.theme.lower().replace(" ", "_")

            for platform, post in plan.posts.items():
                profile = PLATFORM_PROFILES[platform]
                filename = f"{profile.prefix}_{date_str}_{topic}.md"
                filepath = Config.DRAFTS_DIR / filename

                # Validate content
                if not self._validate_draft(post):
                    self._log(f"Invalid draft skipped: {filename}", "WARN")
                    continue

                # Generate file content
                content = self._format_draft_file(plan, platform, post)

                # Save
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    drafts_saved += 1
                    self._log(f"Saved: {filename}")
                except Exception as e:
                    self._log(f"Error saving {filename}: {e}", "ERROR")

        self._log(f"Total drafts saved: {drafts_saved}")

        return drafts_saved

    def _validate_draft(self, post: PlatformPost) -> bool:
        """Validate draft before saving."""
        # Check minimum length
        if post.content_length < Config.MIN_POST_LENGTH:
            return False

        # Check for placeholder text
        placeholders = ["[PLACEHOLDER]", "[TODO]", "[INSERT", "{{", "}}"]
        for p in placeholders:
            if p in post.content:
                return False

        # Check not empty
        if not post.content.strip():
            return False

        return True

    def _format_draft_file(
        self,
        plan: DailyPlan,
        platform: Platform,
        post: PlatformPost
    ) -> str:
        """Format draft as markdown file."""
        profile = PLATFORM_PROFILES[platform]

        lines = [
            "---",
            f"platform: {platform.value}",
            f"date: {plan.theme.date.strftime('%Y-%m-%d')}",
            f"suggested_time: {post.suggested_time}",
            f"theme: {plan.theme.theme}",
            f"status: draft",
            f"generated: {datetime.now().isoformat()}",
            "---",
            "",
            f"# {plan.theme.theme}",
            "",
            post.content,
            "",
        ]

        if post.hashtags:
            lines.append(" ".join(post.hashtags))
            lines.append("")

        if post.media_suggestion:
            lines.append(f"<!-- Media suggestion: {post.media_suggestion} -->")
            lines.append("")

        if post.cta:
            lines.append(f"<!-- CTA: {post.cta} -->")

        return "\n".join(lines)

    def generate_ceo_brief(self, strategy: CampaignStrategy) -> str:
        """Generate executive summary for CEO brief."""
        self._log("Generating CEO brief...")

        # Ensure directory exists
        Config.EXECUTIVE_DIR.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"weekly_campaign_brief_{date_str}.md"
        filepath = Config.EXECUTIVE_DIR / filename

        # Generate content
        content = self._format_ceo_brief(strategy)

        # Save
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self._log(f"CEO brief saved: {filename}")
            return str(filepath)
        except Exception as e:
            self._log(f"Error saving CEO brief: {e}", "ERROR")
            return ""

    def _format_ceo_brief(self, strategy: CampaignStrategy) -> str:
        """Format CEO executive brief."""
        lines = [
            "# Weekly Campaign Brief",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Campaign Period:** {strategy.start_date.strftime('%Y-%m-%d')} to {strategy.end_date.strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
            "## Strategic Goal Summary",
            "",
            f"**Primary Goal:** {strategy.goals.primary_goal}",
            f"**Target Audience:** {strategy.goals.target_audience}",
            f"**Weekly Focus:** {strategy.goals.weekly_focus}",
            f"**Brand Tone:** {strategy.goals.tone}",
            "",
            "---",
            "",
            "## Weekly Narrative",
            "",
            strategy.weekly_narrative,
            "",
            "---",
            "",
            "## Platform Focus",
            "",
        ]

        for platform in Platform:
            profile = PLATFORM_PROFILES[platform]
            lines.append(f"### {profile.name}")
            lines.append(f"- **Tone:** {profile.tone_modifier}")
            lines.append(f"- **Style:** {profile.content_style}")
            lines.append(f"- **Best Times:** {', '.join(profile.best_times)}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Content Volume Summary",
            "",
            f"- **Total Posts:** {strategy.total_posts}",
            f"- **Posts per Day:** {strategy.total_posts // 7}",
            f"- **Platforms:** {', '.join(strategy.platforms_covered)}",
            "",
            "### Daily Themes",
            "",
        ])

        for plan in strategy.daily_plans:
            lines.append(f"- **Day {plan.theme.day_number}** ({plan.theme.date.strftime('%A')}): {plan.theme.theme}")

        lines.extend([
            "",
            "---",
            "",
            "## Expected Impact",
            "",
            strategy.expected_impact,
            "",
            "---",
            "",
            "## Risk Notes",
            "",
        ])

        for risk in strategy.risk_notes:
            lines.append(f"- {risk}")

        lines.extend([
            "",
            "---",
            "",
            "## Next Steps",
            "",
            "1. Review generated drafts in `AI_Employee_Vault/Drafts/`",
            "2. Approve posts for publishing via approval workflow",
            "3. Monitor engagement metrics post-publication",
            "",
            "---",
            "",
            "*Generated by Social Campaign Engine - Gold Tier Strategic Layer*",
        ])

        return "\n".join(lines)

    def run(self, start_date: Optional[datetime] = None) -> int:
        """Execute the campaign generation workflow."""
        self._log("=" * 60)
        self._log("Social Campaign Engine - Gold Tier Strategic Layer")
        self._log("=" * 60)

        # Audit log start
        self._audit_log(
            action="campaign_generation_started",
            target="weekly_campaign",
            result=ResultStatus.PENDING
        )

        # Load business goals
        if not self.load_business_goals():
            self._audit_log(
                action="campaign_generation_failed",
                target="weekly_campaign",
                result=ResultStatus.FAILURE,
                error="Missing business goals file"
            )
            return ExitCode.MISSING_GOALS

        # Load analytics (optional)
        self.load_analytics_if_available()

        # Determine start date
        if start_date is None:
            start_date = datetime.now() + timedelta(days=1)

        self._log(f"Campaign start date: {start_date.strftime('%Y-%m-%d')}")

        try:
            # Generate strategy
            strategy = self.generate_campaign_strategy(start_date)

            # Save drafts
            drafts_count = self.save_drafts(strategy)

            if drafts_count == 0:
                self._audit_log(
                    action="campaign_generation_failed",
                    target="weekly_campaign",
                    result=ResultStatus.FAILURE,
                    error="No drafts generated"
                )
                return ExitCode.GENERATION_FAILURE

            # Generate CEO brief
            brief_path = self.generate_ceo_brief(strategy)

            # Success
            self._log("=" * 60)
            self._log("CAMPAIGN GENERATION COMPLETE")
            self._log("=" * 60)
            self._log(f"Drafts generated: {drafts_count}")
            self._log(f"CEO brief: {brief_path}")
            self._log(f"Draft location: {Config.DRAFTS_DIR}")
            self._log("=" * 60)

            self._audit_log(
                action="campaign_generation_completed",
                target="weekly_campaign",
                parameters={
                    "drafts_generated": drafts_count,
                    "platforms": strategy.platforms_covered,
                    "start_date": start_date.isoformat(),
                },
                result=ResultStatus.SUCCESS
            )

            return ExitCode.SUCCESS

        except Exception as e:
            self._log(f"Generation failed: {e}", "ERROR")
            self._audit_log(
                action="campaign_generation_failed",
                target="weekly_campaign",
                result=ResultStatus.FAILURE,
                error=str(e)
            )
            return ExitCode.GENERATION_FAILURE


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Social Campaign Engine - AI-Powered Strategic Planning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0 - Success
  1 - Missing goals file
  2 - Generation failure

Examples:
  python3 scripts/social_campaign_engine.py
  python3 scripts/social_campaign_engine.py --week
  python3 scripts/social_campaign_engine.py --verbose
        """
    )

    parser.add_argument(
        '--week',
        action='store_true',
        help='Generate for next 7 days (default behavior)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    engine = SocialCampaignEngine(verbose=args.verbose)
    exit_code = engine.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

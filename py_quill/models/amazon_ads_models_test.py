"""Tests for Amazon Ads models."""

from __future__ import annotations

import datetime

import pytest
from models import amazon_ads_models


def test_amazon_campaign_ensure_key_is_deterministic():
  campaign = amazon_ads_models.AmazonCampaign(
    profile_id="profile-1",
    profile_country="US",
    region="na",
    campaign_id="campaign-1",
    campaign_name="Campaign 1",
    campaign_status="ENABLED",
    currency_code="USD",
  )

  key = campaign.ensure_key()

  assert key == "profile-1__campaign-1"
  assert campaign.ensure_key() == key


def test_amazon_campaign_to_dict_round_trips():
  created_at = datetime.datetime(2026,
                                 3,
                                 8,
                                 12,
                                 0,
                                 tzinfo=datetime.timezone.utc)
  updated_at = datetime.datetime(2026,
                                 3,
                                 8,
                                 12,
                                 5,
                                 tzinfo=datetime.timezone.utc)
  campaign = amazon_ads_models.AmazonCampaign(
    key="profile-1__campaign-1",
    profile_id="profile-1",
    profile_country="US",
    region="na",
    campaign_id="campaign-1",
    campaign_name="Campaign 1",
    campaign_status="enabled",
    currency_code="usd",
    created_at=created_at,
    updated_at=updated_at,
  )

  restored = amazon_ads_models.AmazonCampaign.from_dict(
    campaign.to_dict(include_key=False),
    key=campaign.key,
  )

  assert restored.key == "profile-1__campaign-1"
  assert restored.profile_id == "profile-1"
  assert restored.profile_country == "US"
  assert restored.region == "na"
  assert restored.campaign_id == "campaign-1"
  assert restored.campaign_name == "Campaign 1"
  assert restored.campaign_status == "ENABLED"
  assert restored.currency_code == "usd"
  assert restored.created_at == created_at
  assert restored.updated_at == updated_at


def test_amazon_campaign_from_dict_missing_required_fields_raise():
  with pytest.raises(ValueError,
                     match="AmazonCampaign.profile_id is required"):
    amazon_ads_models.AmazonCampaign.from_dict({
      "campaign_id": "campaign-1",
      "campaign_name": "Campaign 1",
      "campaign_status": "ENABLED",
    })

  with pytest.raises(ValueError,
                     match="AmazonCampaign.campaign_status is required"):
    amazon_ads_models.AmazonCampaign.from_dict({
      "profile_id": "profile-1",
      "campaign_id": "campaign-1",
      "campaign_name": "Campaign 1",
    })

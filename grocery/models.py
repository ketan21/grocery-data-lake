"""Pydantic models for AH product data."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class Image(BaseModel):
    width: int
    height: int
    url: str


class DiscountLabel(BaseModel):
    code: str
    default_description: str | None = Field(alias="defaultDescription", default=None)
    percentage: float | None = None
    amount: float | None = None
    count: int | None = None
    free_count: int | None = Field(alias="freeCount", default=None)


class Product(BaseModel):
    """Product from search endpoint (52 fields)."""
    webshop_id: int = Field(alias="webshopId")
    hq_id: int = Field(alias="hqId")
    title: str
    brand: str | None = None
    sales_unit_size: str | None = Field(alias="salesUnitSize", default=None)
    unit_price_description: str | None = Field(alias="unitPriceDescription", default=None)
    images: list[Image] | None = None
    bonus_start_date: str | None = Field(alias="bonusStartDate", default=None)
    bonus_end_date: str | None = Field(alias="bonusEndDate", default=None)
    discount_type: str | None = Field(alias="discountType", default=None)
    segment_type: str | None = Field(alias="segmentType", default=None)
    promotion_type: str | None = Field(alias="promotionType", default=None)
    bonus_mechanism: str | None = Field(alias="bonusMechanism", default=None)
    current_price: float | None = Field(alias="currentPrice", default=None)
    price_before_bonus: float | None = Field(alias="priceBeforeBonus", default=None)
    order_availability_status: str | None = Field(alias="orderAvailabilityStatus", default=None)
    order_availability_description: str | None = Field(alias="orderAvailabilityDescription", default=None)
    main_category: str | None = Field(alias="mainCategory", default=None)
    sub_category: str | None = Field(alias="subCategory", default=None)
    shop_type: str | None = Field(alias="shopType", default=None)
    bonus_period_description: str | None = Field(alias="bonusPeriodDescription", default=None)
    available_online: bool | None = Field(alias="availableOnline", default=None)
    is_previously_bought: bool | None = Field(alias="isPreviouslyBought", default=None)
    description_highlights: str | None = Field(alias="descriptionHighlights", default=None)
    property_icons: list[Any] | None = Field(alias="propertyIcons", default=None)
    stickers: Any | None = None
    nutriscore: str | None = None
    nix18: bool | None = None
    is_stapel_bonus: bool | None = Field(alias="isStapelBonus", default=None)
    extra_descriptions: list[Any] | None = Field(alias="extraDescriptions", default=None)
    bonus_segment_id: str | int | None = Field(alias="bonusSegmentId", default=None)
    bonus_segment_description: str | None = Field(alias="bonusSegmentDescription", default=None)
    is_bonus: bool | None = Field(alias="isBonus", default=None)
    has_list_price: bool | None = Field(alias="hasListPrice", default=None)
    description_full: str | None = Field(alias="descriptionFull", default=None)
    is_orderable: bool | None = Field(alias="isOrderable", default=None)
    is_infinite_bonus: bool | None = Field(alias="isInfiniteBonus", default=None)
    is_sample: bool | None = Field(alias="isSample", default=None)
    is_bonus_price: bool | None = Field(alias="isBonusPrice", default=None)
    is_sponsored: bool | None = Field(alias="isSponsored", default=None)
    auction_id: str | None = Field(alias="auctionId", default=None)
    is_virtual_bundle: bool | None = Field(alias="isVirtualBundle", default=None)
    virtual_bundle_items: list[Any] | None = Field(alias="virtualBundleItems", default=None)
    product_count: int | None = Field(alias="productCount", default=None)
    multiple_item_promotion: bool | None = Field(alias="multipleItemPromotion", default=None)
    label_type: str | None = Field(alias="labelType", default=None)
    discount_labels: list[DiscountLabel] | None = Field(alias="discountLabels", default=None)
    is_favorite: bool | None = Field(alias="isFavorite", default=None)
    external_webshop_url: str | None = Field(alias="externalWebshopUrl", default=None)
    min_best_before_days: int | None = Field(alias="minBestBeforeDays", default=None)
    medical_device_type_code: str | None = Field(alias="medicalDeviceTypeCode", default=None)
    medicine_type_code: str | None = Field(alias="medicineTypeCode", default=None)

    model_config = {"populate_by_name": True}


class Category(BaseModel):
    id: int
    name: str


class NutrientQuantity(BaseModel):
    value: float | None
    measurement_unit_code: dict | None = Field(alias="measurementUnitCode")


class Nutrient(BaseModel):
    nutrient_type_code: dict | None = Field(alias="nutrientTypeCode")
    quantity_contained: list[NutrientQuantity] | None = Field(alias="quantityContained")


class NutrientHeader(BaseModel):
    nutrient_basis_quantity: dict | None = Field(alias="nutrientBasisQuantity")
    nutrient_detail: list[Nutrient] | None = Field(alias="nutrientDetail")


class NutritionalInformation(BaseModel):
    nutrient_headers: list[NutrientHeader] | None = Field(alias="nutrientHeaders")


class AllergenItem(BaseModel):
    type_code: dict | None = Field(alias="typeCode")


class AllergenInformation(BaseModel):
    items: list[AllergenItem] | None


class NutritionAllergenDetail(BaseModel):
    """Enriched detail from /detail/v4/fir/{id}."""
    product_id: int | None = Field(alias="productId")
    nutritional_information: NutritionalInformation | None = Field(alias="nutritionalInformation")
    allergen_information: list[AllergenInformation] | None = Field(alias="allergenInformation")
    properties: dict[str, Any] | None = None

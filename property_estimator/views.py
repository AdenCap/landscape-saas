import base64
import json
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponse

from accounts.decorators import role_required
from accounts.utils import get_business as _get_business
from customers.models import Customer, Property
from .models import PropertyEstimate, PropertyEstimateImage
from .analysis import analyze_image, HAS_OPENCV


@role_required("owner", "manager")
def estimator_index(request):
    """Landing page for Estimator tools: property estimates, fertilizer calculator, mulch/rock calculator."""
    # Redirect to estimates page with estimator tools accessible via tabs
    return render(request, "property_estimator/estimator_index.html")


@role_required("owner", "manager")
def estimator_list(request):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    estimates = PropertyEstimate.objects.filter(
        property__customer__business=business
    ).select_related('property', 'property__customer').order_by('-updated_at')[:50]
    return render(request, "property_estimator/estimator_list.html", {"estimates": estimates})


@role_required("owner", "manager")
def fertilizer_calculator(request):
    """Standalone fertilizer calculator: lbs per 1k sq ft, total sq ft, pricing per lb or per bag."""
    from billing.models import FertilizerProduct
    business = _get_business(request)
    customers = []
    products = []
    if business:
        customers = Customer.objects.filter(business=business).order_by("name")
        products = FertilizerProduct.objects.filter(business=business, active=True).order_by("name")
    return render(request, "property_estimator/fertilizer_calculator.html", {
        "customers": customers,
        "products": products,
    })


@role_required("owner", "manager")
def mulch_rock_calculator(request):
    """Standalone mulch and rock calculator: sq ft, depth, pricing per bag or per cubic yard."""
    business = _get_business(request)
    customers = []
    if business:
        customers = Customer.objects.filter(business=business).order_by("name")
    return render(request, "property_estimator/mulch_rock_calculator.html", {"customers": customers})


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def estimator_new(request, property_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    prop = get_object_or_404(Property, id=property_id, customer__business=business)

    if request.method == "POST":
        estimate = PropertyEstimate.objects.create(property=prop)
        return redirect("estimator_detail", property_id=property_id, estimate_id=estimate.id)

    existing = PropertyEstimate.objects.filter(property=prop).order_by('-updated_at').first()
    if existing:
        return redirect("estimator_detail", property_id=property_id, estimate_id=existing.id)

    return render(request, "property_estimator/estimator_new.html", {"property": prop})


@role_required("owner", "manager")
def estimator_detail(request, property_id, estimate_id):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    prop = get_object_or_404(Property, id=property_id, customer__business=business)
    estimate = get_object_or_404(PropertyEstimate, id=estimate_id, property=prop)
    images = estimate.images.all()

    # Aggregate from analyzed images when estimate has no saved values
    agg = {"grass_sqft": Decimal("0"), "pavement_sqft": Decimal("0"), "mulch_sqft": Decimal("0"), "tree_count": 0, "bush_count": 0}
    if not any([estimate.grass_sqft, estimate.pavement_sqft, estimate.mulch_bed_sqft]) and images:
        for img in images:
            if img.pixel_scale and img.raw_grass_pixels is not None:
                try:
                    agg["grass_sqft"] += Decimal(str(img.raw_grass_pixels or 0)) * img.pixel_scale
                    agg["pavement_sqft"] += Decimal(str(img.raw_pavement_pixels or 0)) * img.pixel_scale
                    agg["mulch_sqft"] += Decimal(str(img.raw_mulch_pixels or 0)) * img.pixel_scale
                    agg["tree_count"] += img.raw_tree_count or 0
                    agg["bush_count"] += img.raw_bush_count or 0
                except (InvalidOperation, TypeError, ValueError):
                    pass
    has_mapbox = bool(getattr(settings, "MAPBOX_ACCESS_TOKEN", "") or "")
    return render(request, "property_estimator/estimator_detail.html", {
        "property": prop,
        "estimate": estimate,
        "images": images,
        "has_opencv": HAS_OPENCV,
        "has_mapbox": has_mapbox,
        "aggregated": agg,
    })


@role_required("owner", "manager")
@require_POST
def estimator_upload(request, property_id, estimate_id):
    business = _get_business(request)
    if not business:
        return redirect("/")
    prop = get_object_or_404(Property, id=property_id, customer__business=business)
    estimate = get_object_or_404(PropertyEstimate, id=estimate_id, property=prop)

    image_file = request.FILES.get("image")
    if not image_file:
        messages.error(request, "No image selected.")
        return redirect("estimator_detail", property_id=property_id, estimate_id=estimate_id)

    order = estimate.images.count()
    img = PropertyEstimateImage.objects.create(estimate=estimate, image=image_file, order=order)
    messages.success(request, "Image uploaded. Run analysis to detect grass, pavement, mulch, trees, and bushes.")
    return redirect("estimator_detail", property_id=property_id, estimate_id=estimate_id)


@role_required("owner", "manager")
@require_http_methods(["GET", "POST"])
def estimator_analyze(request, property_id, estimate_id, image_id):
    business = _get_business(request)
    if not business:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    prop = get_object_or_404(Property, id=property_id, customer__business=business)
    estimate = get_object_or_404(PropertyEstimate, id=estimate_id, property=prop)
    img = get_object_or_404(PropertyEstimateImage, id=image_id, estimate=estimate)

    total_area = None
    if request.method == "POST":
        data = json.loads(request.body) if request.body else {}
        total_area = data.get("total_area_sqft")
    total_area = total_area or (float(estimate.total_area_sqft) if estimate.total_area_sqft else None)

    result = analyze_image(img.image.path, total_area_sqft=total_area, enhance=True)
    if "error" in result:
        return JsonResponse({"error": result["error"], **{k: result.get(k, 0) for k in ("grass_pixels", "pavement_pixels", "mulch_pixels", "tree_count", "bush_count")}})

    # Store raw results on image
    img.raw_grass_pixels = result.get("grass_pixels", 0)
    img.raw_pavement_pixels = result.get("pavement_pixels", 0)
    img.raw_mulch_pixels = result.get("mulch_pixels", 0)
    img.raw_tree_count = result.get("tree_count", 0)
    img.raw_bush_count = result.get("bush_count", 0)
    if result.get("pixel_scale"):
        img.pixel_scale = Decimal(str(result["pixel_scale"]))
    img.save()

    if result.get("overlay_png"):
        img.segmentation_overlay.save(f"overlay_{img.id}.png", ContentFile(result["overlay_png"]), save=True)
    if result.get("enhanced_png"):
        img.enhanced_image.save(f"enhanced_{img.id}.png", ContentFile(result["enhanced_png"]), save=True)

    payload = {
        "grass_pixels": result.get("grass_pixels", 0),
        "pavement_pixels": result.get("pavement_pixels", 0),
        "mulch_pixels": result.get("mulch_pixels", 0),
        "tree_count": result.get("tree_count", 0),
        "bush_count": result.get("bush_count", 0),
        "grass_sqft": result.get("grass_sqft"),
        "pavement_sqft": result.get("pavement_sqft"),
        "mulch_sqft": result.get("mulch_sqft"),
        "overlay_url": img.segmentation_overlay.url if img.segmentation_overlay else None,
    }
    return JsonResponse(payload)


@role_required("owner", "manager")
@require_POST
def estimator_save(request, property_id, estimate_id):
    business = _get_business(request)
    if not business:
        return redirect("/")
    prop = get_object_or_404(Property, id=property_id, customer__business=business)
    estimate = get_object_or_404(PropertyEstimate, id=estimate_id, property=prop)

    total = request.POST.get("total_area_sqft")
    if total:
        try:
            estimate.total_area_sqft = Decimal(total)
        except Exception:
            pass

    for key in ("grass_sqft", "pavement_sqft", "mulch_bed_sqft", "tree_count", "bush_count"):
        val = request.POST.get(key)
        if val is not None and val != "":
            try:
                if key in ("tree_count", "bush_count"):
                    setattr(estimate, key, int(float(val)))
                else:
                    setattr(estimate, key, Decimal(val))
            except (ValueError, TypeError):
                pass
    estimate.notes = request.POST.get("notes", "")[:1000]
    estimate.save()

    messages.success(request, "Estimate saved.")
    return redirect("estimator_detail", property_id=property_id, estimate_id=estimate_id)


def _geocode_address(address):
    """Return (lat, lng) for address, or None."""
    try:
        from geopy.geocoders import Nominatim
        from geopy.extra.rate_limiter import RateLimiter
        geolocator = Nominatim(user_agent="field-ops-estimator")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.0)
        location = geocode(address)
        if location:
            return (float(location.latitude), float(location.longitude))
    except Exception:
        pass
    return None


@role_required("owner", "manager")
def estimator_satellite_image(request, property_id):
    """Serve satellite/aerial image for property address. Geocodes if needed, uses Mapbox."""
    business = _get_business(request)
    if not business:
        return HttpResponse(status=403)
    prop = get_object_or_404(Property, id=property_id, customer__business=business)

    lat, lng = None, None
    if prop.latitude is not None and prop.longitude is not None:
        lat, lng = float(prop.latitude), float(prop.longitude)
    if lat is None and prop.address:
        coords = _geocode_address(prop.address)
        if coords:
            lat, lng = coords
            prop.latitude = Decimal(str(lat))
            prop.longitude = Decimal(str(lng))
            prop.save()

    if lat is None or lng is None:
        return HttpResponse("Address could not be geocoded. Add coordinates in the property settings.", status=400)

    token = getattr(settings, "MAPBOX_ACCESS_TOKEN", "") or ""
    if not token:
        return HttpResponse(
            "Mapbox token not configured. Set MAPBOX_ACCESS_TOKEN in environment for satellite imagery.",
            status=503,
        )

    try:
        import requests
        url = (
            f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
            f"{lng},{lat},18,0,60/800x600@2x?access_token={token}"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return HttpResponse(resp.content, content_type="image/png")
    except Exception as e:
        return HttpResponse(f"Could not fetch satellite image: {e}", status=502)

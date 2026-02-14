import base64
import json
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse

from accounts.decorators import role_required
from customers.models import Property
from .models import PropertyEstimate, PropertyEstimateImage
from .analysis import analyze_image, HAS_OPENCV


def _get_business(request):
    return getattr(request.user, 'business', None)


@role_required("owner")
def estimator_list(request):
    business = _get_business(request)
    if not business:
        messages.error(request, "You must be associated with a business.")
        return redirect("/")
    estimates = PropertyEstimate.objects.filter(
        property__customer__business=business
    ).select_related('property', 'property__customer').order_by('-updated_at')[:50]
    return render(request, "property_estimator/estimator_list.html", {"estimates": estimates})


@role_required("owner")
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


@role_required("owner")
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
    return render(request, "property_estimator/estimator_detail.html", {
        "property": prop,
        "estimate": estimate,
        "images": images,
        "has_opencv": HAS_OPENCV,
        "aggregated": agg,
    })


@role_required("owner")
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


@role_required("owner")
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


@role_required("owner")
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

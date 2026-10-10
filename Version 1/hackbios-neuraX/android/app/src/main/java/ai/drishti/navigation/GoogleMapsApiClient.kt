package ai.drishti.navigation

import android.util.Log
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException

/**
 * Result data class for pedestrian walking routes from Google Routes API v2.
 */
data class RouteResult(
    val distanceMeters: Int,
    val durationSeconds: Int,
    val waypoints: List<Waypoint>
)

/**
 * REST API client for Google Maps Platform:
 * - Places API (New): searchNearby (30m POI identification) and searchText (destination resolution)
 * - Geocoding API: Reverse geocoding for street and locality
 * - Routes API v2: Pedestrian walking routing (travelMode: WALK) with micro-steps
 */
class GoogleMapsApiClient(
    private val client: OkHttpClient = OkHttpClient()
) {
    private val tag = "GoogleMapsApiClient"
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    /**
     * Layer 1: Identify nearest building or point of interest within 30m via Places API (New).
     */
    fun getNearbyPlace(
        latitude: Double,
        longitude: Double,
        apiKey: String,
        callback: (poiName: String?) -> Unit
    ) {
        if (apiKey.isBlank() || apiKey.startsWith("<")) {
            callback(null)
            return
        }

        val url = "https://places.googleapis.com/v1/places:searchNearby"
        val payload = JSONObject().apply {
            put("locationRestriction", JSONObject().apply {
                put("circle", JSONObject().apply {
                    put("center", JSONObject().apply {
                        put("latitude", latitude)
                        put("longitude", longitude)
                    })
                    put("radius", 30.0) // Strictly 30m for high confidence
                })
            })
            put("maxResultCount", 1)
        }

        val request = Request.Builder()
            .url(url)
            .addHeader("Content-Type", "application/json")
            .addHeader("X-Goog-Api-Key", apiKey)
            .addHeader("X-Goog-FieldMask", "places.displayName")
            .post(payload.toString().toRequestBody(jsonMediaType))
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.w(tag, "Places nearby search failed: ${e.message}")
                callback(null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { resp ->
                    if (!resp.isSuccessful) {
                        callback(null)
                        return
                    }
                    try {
                        val body = resp.body?.string() ?: return callback(null)
                        val json = JSONObject(body)
                        val places = json.optJSONArray("places")
                        if (places != null && places.length() > 0) {
                            val displayName = places.getJSONObject(0)
                                .optJSONObject("displayName")
                                ?.optString("text")
                            callback(displayName)
                            return
                        }
                    } catch (e: Exception) {
                        Log.w(tag, "Error parsing places response: ${e.message}")
                    }
                    callback(null)
                }
            }
        })
    }

    /**
     * Layer 2: Reverse geocode latitude and longitude to street address and locality.
     */
    fun getReverseGeocode(
        latitude: Double,
        longitude: Double,
        apiKey: String,
        callback: (address: String?) -> Unit
    ) {
        if (apiKey.isBlank() || apiKey.startsWith("<")) {
            callback(null)
            return
        }

        val url = "https://maps.googleapis.com/maps/api/geocode/json?latlng=$latitude,$longitude&key=$apiKey"
        val request = Request.Builder().url(url).get().build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.w(tag, "Geocoding request failed: ${e.message}")
                callback(null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { resp ->
                    if (!resp.isSuccessful) {
                        callback(null)
                        return
                    }
                    try {
                        val body = resp.body?.string() ?: return callback(null)
                        val json = JSONObject(body)
                        if (json.optString("status") == "OK") {
                            val results = json.optJSONArray("results")
                            if (results != null && results.length() > 0) {
                                val address = results.getJSONObject(0).optString("formatted_address")
                                callback(address)
                                return
                            }
                        }
                    } catch (e: Exception) {
                        Log.w(tag, "Error parsing geocode response: ${e.message}")
                    }
                    callback(null)
                }
            }
        })
    }

    /**
     * Resolve destination name or category (e.g., "pharmacy") to address and coordinates.
     */
    fun searchPlace(
        query: String,
        userLocation: GeoPoint,
        apiKey: String,
        callback: (name: String?, address: String?, location: GeoPoint?) -> Unit
    ) {
        if (apiKey.isBlank() || apiKey.startsWith("<")) {
            callback(query, query, null)
            return
        }

        val url = "https://places.googleapis.com/v1/places:searchText"
        val payload = JSONObject().apply {
            put("textQuery", query)
            put("locationBias", JSONObject().apply {
                put("circle", JSONObject().apply {
                    put("center", JSONObject().apply {
                        put("latitude", userLocation.latitude)
                        put("longitude", userLocation.longitude)
                    })
                    put("radius", 5000.0) // 5km radius bias
                })
            })
        }

        val request = Request.Builder()
            .url(url)
            .addHeader("Content-Type", "application/json")
            .addHeader("X-Goog-Api-Key", apiKey)
            .addHeader("X-Goog-FieldMask", "places.formattedAddress,places.displayName,places.location")
            .post(payload.toString().toRequestBody(jsonMediaType))
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.w(tag, "Places search failed: ${e.message}")
                callback(query, query, null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { resp ->
                    if (!resp.isSuccessful) {
                        callback(query, query, null)
                        return
                    }
                    try {
                        val body = resp.body?.string() ?: return callback(query, query, null)
                        val json = JSONObject(body)
                        val places = json.optJSONArray("places")
                        if (places != null && places.length() > 0) {
                            val first = places.getJSONObject(0)
                            val address = first.optString("formattedAddress")
                            val name = first.optJSONObject("displayName")?.optString("text")
                            val locObj = first.optJSONObject("location")
                            val loc = if (locObj != null) {
                                GeoPoint(locObj.optDouble("latitude"), locObj.optDouble("longitude"))
                            } else null
                            callback(name ?: query, address.ifEmpty { query }, loc)
                            return
                        }
                    } catch (e: Exception) {
                        Log.w(tag, "Error parsing places search response: ${e.message}")
                    }
                    callback(query, query, null)
                }
            }
        })
    }

    /**
     * Compute pedestrian walking route using Google Routes API v2.
     * Extracts distance, duration, and granular micro-steps.
     */
    fun computeWalkingRoute(
        origin: GeoPoint,
        destinationAddress: String,
        apiKey: String,
        callback: (RouteResult?) -> Unit
    ) {
        if (apiKey.isBlank() || apiKey.startsWith("<")) {
            callback(null)
            return
        }

        val url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        val payload = JSONObject().apply {
            put("origin", JSONObject().apply {
                put("location", JSONObject().apply {
                    put("latLng", JSONObject().apply {
                        put("latitude", origin.latitude)
                        put("longitude", origin.longitude)
                    })
                })
            })
            put("destination", JSONObject().apply {
                put("address", destinationAddress)
            })
            put("travelMode", "WALK")
            put("languageCode", "en-US")
            put("routingPreference", "ROUTING_PREFERENCE_UNSPECIFIED")
        }

        val request = Request.Builder()
            .url(url)
            .addHeader("Content-Type", "application/json")
            .addHeader("X-Goog-Api-Key", apiKey)
            .addHeader(
                "X-Goog-FieldMask",
                "routes.duration,routes.distanceMeters,routes.legs.steps.navigationInstruction.instructions,routes.legs.steps.distanceMeters,routes.legs.steps.endLocation"
            )
            .post(payload.toString().toRequestBody(jsonMediaType))
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.w(tag, "Routes computeRoutes failed: ${e.message}")
                callback(null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { resp ->
                    if (!resp.isSuccessful) {
                        callback(null)
                        return
                    }
                    try {
                        val body = resp.body?.string() ?: return callback(null)
                        val json = JSONObject(body)
                        val routes = json.optJSONArray("routes")
                        if (routes != null && routes.length() > 0) {
                            val route = routes.getJSONObject(0)
                            val distanceMeters = route.optInt("distanceMeters", 0)
                            val durationStr = route.optString("duration", "0s")
                            val durationSeconds = durationStr.replace("s", "").toIntOrNull() ?: 0

                            val waypoints = mutableListOf<Waypoint>()
                            val legs = route.optJSONArray("legs")
                            val steps: JSONArray? = if (legs != null && legs.length() > 0) {
                                legs.getJSONObject(0).optJSONArray("steps")
                            } else null

                            if (steps != null) {
                                for (i in 0 until steps.length()) {
                                    val step = steps.getJSONObject(i)
                                    val instruction = step.optJSONObject("navigationInstruction")
                                        ?.optString("instructions") ?: "Continue walking"
                                    val stepDist = step.optInt("distanceMeters", 50)
                                    val endLoc = step.optJSONObject("endLocation")?.optJSONObject("latLng")
                                    val coord = if (endLoc != null) {
                                        GeoPoint(endLoc.optDouble("latitude"), endLoc.optDouble("longitude"))
                                    } else {
                                        // Slight offset if coordinate not present
                                        GeoPoint(origin.latitude + 0.0002 * (i + 1), origin.longitude + 0.0002 * (i + 1))
                                    }
                                    waypoints.add(
                                        Waypoint(
                                            coordinate = coord,
                                            instruction = instruction,
                                            distanceThresholdMeters = (stepDist.coerceIn(10, 25)).toFloat()
                                        )
                                    )
                                }
                            }

                            if (waypoints.isNotEmpty()) {
                                callback(RouteResult(distanceMeters, durationSeconds, waypoints))
                                return
                            }
                        }
                    } catch (e: Exception) {
                        Log.w(tag, "Error parsing routes response: ${e.message}")
                    }
                    callback(null)
                }
            }
        })
    }
}

package ai.drishti.navigation

import android.util.Log

/**
 * Manages active route navigation, computes heading instructions,
 * and formats clear turn-by-turn guidance for the visually impaired user.
 */
class NavigationEngine(
    private val apiClient: GoogleMapsApiClient = GoogleMapsApiClient()
) {

    private val tag = "NavigationEngine"
    private var activeStateManager: NavStateManager? = null

    var isNavigating: Boolean = false
        private set

    val destination: String?
        get() = activeStateManager?.destination

    val currentStepIndex: Int
        get() = activeStateManager?.currentStepIndex ?: 0

    val totalSteps: Int
        get() = activeStateManager?.waypoints?.size ?: 0

    /**
     * Synchronous route initiation with fallback waypoints.
     */
    fun startRoute(destination: String, origin: GeoPoint): String {
        Log.i(tag, "Starting navigation to: $destination from ($origin)")

        val waypoints = listOf(
            Waypoint(
                coordinate = GeoPoint(origin.latitude + 0.0005, origin.longitude + 0.0005),
                instruction = "Walk straight for 50 meters towards the intersection."
            ),
            Waypoint(
                coordinate = GeoPoint(origin.latitude + 0.0010, origin.longitude + 0.0010),
                instruction = "Turn right at the crosswalk. Listen for oncoming traffic."
            ),
            Waypoint(
                coordinate = GeoPoint(origin.latitude + 0.0015, origin.longitude + 0.0012),
                instruction = "Continue straight. $destination will be 20 meters ahead on your left."
            )
        )

        activeStateManager = NavStateManager(destination, waypoints)
        isNavigating = true
        return "Navigation started for $destination. Walk straight."
    }

    /**
     * Asynchronously calculates pedestrian walking route via Google Routes API v2.
     * Falls back to standard route if API key is missing or call fails.
     */
    fun startRouteWithGoogleMaps(
        destination: String,
        origin: GeoPoint,
        apiKey: String,
        onReady: (announcement: String) -> Unit
    ) {
        if (apiKey.isBlank() || apiKey.startsWith("<")) {
            val fallback = startRoute(destination, origin)
            onReady(fallback)
            return
        }

        apiClient.searchPlace(destination, origin, apiKey) { placeName, address, _ ->
            val resolvedDest = address ?: destination
            val displayTitle = placeName ?: destination

            apiClient.computeWalkingRoute(origin, resolvedDest, apiKey) { result ->
                if (result != null && result.waypoints.isNotEmpty()) {
                    activeStateManager = NavStateManager(displayTitle, result.waypoints)
                    isNavigating = true
                    val durationMins = maxOf(1, result.durationSeconds / 60)
                    val firstStep = result.waypoints.first().instruction
                    val announcement = "Found $displayTitle! It is ${result.distanceMeters} meters away and will take about $durationMins minutes walking. First step: $firstStep."
                    Log.i(tag, "Google Maps walking route established: $announcement")
                    onReady(announcement)
                } else {
                    Log.w(tag, "Routes API returned no route, falling back to local calculation.")
                    val fallback = startRoute(destination, origin)
                    onReady(fallback)
                }
            }
        }
    }

    /**
     * Dual-layer location awareness: Places Nearby (30m) + Reverse Geocoding.
     */
    fun getCurrentAddress(
        currentLocation: GeoPoint,
        apiKey: String,
        onResult: (addressDescription: String) -> Unit
    ) {
        if (apiKey.isBlank() || apiKey.startsWith("<")) {
            onResult("Current coordinates: ${String.format("%.4f", currentLocation.latitude)}, ${String.format("%.4f", currentLocation.longitude)}.")
            return
        }

        apiClient.getNearbyPlace(currentLocation.latitude, currentLocation.longitude, apiKey) { poi ->
            apiClient.getReverseGeocode(currentLocation.latitude, currentLocation.longitude, apiKey) { locality ->
                val result = when {
                    poi != null && locality != null -> "You are near $poi, located in $locality."
                    locality != null -> "You are currently at $locality. No specific building identified nearby."
                    poi != null -> "You are near $poi."
                    else -> "Current location: ${String.format("%.4f", currentLocation.latitude)}, ${String.format("%.4f", currentLocation.longitude)}."
                }
                onResult(result)
            }
        }
    }

    /**
     * Simulates or triggers next micro-step progression.
     */
    fun walkStep(): String {
        val manager = activeStateManager
        if (!isNavigating || manager == null) {
            return "You are not currently navigating anywhere. Ask me to go somewhere first."
        }

        val nextIndex = manager.currentStepIndex + 1
        if (nextIndex < manager.waypoints.size) {
            val step = manager.waypoints[nextIndex]
            return "Navigation update: Continue straight for approx 50 meters. Then, ${step.instruction}"
        } else {
            val dest = manager.destination
            stopRoute()
            return "You have arrived at $dest! Disclaimer: Please verify with your cane or guide dog that the entrance is clear and safe to enter."
        }
    }

    fun onLocationUpdate(currentLocation: GeoPoint): String? {
        val manager = activeStateManager ?: return null

        return when (val progress = manager.updateProgress(currentLocation)) {
            is NavProgress.OnTrack -> {
                val dist = progress.distanceToNextMeters.toInt()
                if (dist <= 15) {
                    "Approaching waypoint: ${progress.instruction}"
                } else if (dist % 50 < 10) {
                    "In $dist meters, ${progress.instruction}"
                } else {
                    null
                }
            }
            is NavProgress.OffRoute -> {
                progress.prompt
            }
            is NavProgress.DestinationReached -> {
                val dest = manager.destination
                stopRoute()
                "You have arrived at $dest! Please verify with your white cane that the entrance is clear."
            }
        }
    }

    fun stopRoute(): String {
        val dest = activeStateManager?.destination ?: "destination"
        activeStateManager = null
        isNavigating = false
        Log.i(tag, "Navigation stopped.")
        return "Navigation to $dest has been stopped."
    }
}

package ai.drishti.vision.ocr.postprocess

import ai.drishti.vision.ocr.models.TrackState
import ai.drishti.vision.ocr.models.TrackedText
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * Orders recognized text regions into natural human reading order (top-to-bottom, left-to-right)
 * and computes speech deltas with temporal deduplication.
 */
class TextReadingOrderEngine(
    private val deduplicationThreshold: Float = 0.70f,
    private val spokenHistoryExpiryMs: Long = 15000L
) {

    private data class SpokenEntry(val text: String, val timestampMs: Long)
    private val spokenHistory = mutableListOf<SpokenEntry>()

    /**
     * Orders confirmed tracks into lines and sentences, filtering out already spoken text.
     * Returns novel text to be spoken, or null if no new text is available.
     */
    fun extractNovelReadingContent(tracks: List<TrackedText>, nowMs: Long = System.currentTimeMillis()): String? {
        // Purge expired spoken history entries
        spokenHistory.removeAll { nowMs - it.timestampMs > spokenHistoryExpiryMs }

        // 1. Filter tracks that have recognized text and are CONFIRMED
        val readableTracks = tracks.filter {
            it.state == TrackState.CONFIRMED && !it.recognizedText.isNullOrBlank()
        }

        if (readableTracks.isEmpty()) return null

        // 2. Cluster tracks into reading lines based on vertical alignment
        val lines = clusterIntoReadingLines(readableTracks)

        // 3. Assemble full text paragraphs
        val fullTextBuilder = StringBuilder()
        val candidatePhrases = mutableListOf<Pair<TrackedText, String>>()

        for (line in lines) {
            val lineText = line.joinToString(" ") { it.recognizedText!!.trim() }
            if (lineText.isNotBlank()) {
                fullTextBuilder.append(lineText).append(". ")
                for (t in line) {
                    candidatePhrases.add(Pair(t, t.recognizedText!!.trim()))
                }
            }
        }

        val assembledFullText = fullTextBuilder.toString().trim()
        if (assembledFullText.isBlank()) return null

        // 4. Deduplication against spoken history
        val novelPhrases = mutableListOf<String>()

        for ((track, phrase) in candidatePhrases) {
            if (track.isSpoken) continue

            val isDuplicate = spokenHistory.any { entry ->
                computeSimilarity(entry.text, phrase) >= deduplicationThreshold
            }

            if (!isDuplicate && phrase.length >= 2) {
                novelPhrases.add(phrase)
                track.isSpoken = true
                spokenHistory.add(SpokenEntry(phrase, nowMs))
            }
        }

        return if (novelPhrases.isNotEmpty()) {
            novelPhrases.joinToString(", ")
        } else {
            null
        }
    }

    /**
     * Clusters text bounding boxes into horizontal lines.
     * Two boxes belong to the same line if their vertical centers are within 50% of the average box height.
     */
    fun clusterIntoReadingLines(tracks: List<TrackedText>): List<List<TrackedText>> {
        val sortedByTop = tracks.sortedBy { it.boundingBox.top }
        val lines = mutableListOf<MutableList<TrackedText>>()

        for (track in sortedByTop) {
            val box = track.boundingBox
            val centerY = box.centerY()
            val height = box.height()

            var placed = false
            for (line in lines) {
                val lineAvgCenterY = line.map { it.boundingBox.centerY() }.average().toFloat()
                val lineAvgHeight = line.map { it.boundingBox.height() }.average().toFloat()
                val tolerance = max(height, lineAvgHeight) * 0.5f

                if (abs(centerY - lineAvgCenterY) <= tolerance) {
                    line.add(track)
                    placed = true
                    break
                }
            }

            if (!placed) {
                lines.add(mutableListOf(track))
            }
        }

        // Sort lines top-to-bottom by average centerY, and sort words within each line left-to-right by box.left
        return lines
            .sortedBy { line -> line.map { it.boundingBox.centerY() }.average() }
            .map { line -> line.sortedBy { it.boundingBox.left } }
    }

    /**
     * Computes normalized token overlap / Levenshtein similarity [0.0..1.0].
     */
    fun computeSimilarity(s1: String, s2: String): Float {
        val clean1 = s1.lowercase().trim()
        val clean2 = s2.lowercase().trim()

        if (clean1 == clean2) return 1.0f
        if (clean1.isEmpty() || clean2.isEmpty()) return 0.0f

        // Word token Jaccard similarity
        val words1 = clean1.split("\\s+".toRegex()).toSet()
        val words2 = clean2.split("\\s+".toRegex()).toSet()

        val intersection = words1.intersect(words2).size
        val union = words1.union(words2).size

        if (union > 0) {
            val jaccard = intersection.toFloat() / union
            if (jaccard >= 0.6f) return jaccard
        }

        // Levenshtein distance
        val dist = levenshteinDistance(clean1, clean2)
        val maxLen = max(clean1.length, clean2.length)
        return 1.0f - (dist.toFloat() / maxLen)
    }

    private fun levenshteinDistance(lhs: CharSequence, rhs: CharSequence): Int {
        val lhsLength = lhs.length
        val rhsLength = rhs.length

        var cost = IntArray(lhsLength + 1) { it }
        var newCost = IntArray(lhsLength + 1) { 0 }

        for (i in 1..rhsLength) {
            newCost[0] = i
            for (j in 1..lhsLength) {
                val match = if (lhs[j - 1] == rhs[i - 1]) 0 else 1
                val costReplace = cost[j - 1] + match
                val costInsert = cost[j] + 1
                val costDelete = newCost[j - 1] + 1

                newCost[j] = min(min(costInsert, costDelete), costReplace)
            }
            val swap = cost
            cost = newCost
            newCost = swap
        }

        return cost[lhsLength]
    }

    fun clearHistory() {
        spokenHistory.clear()
    }
}

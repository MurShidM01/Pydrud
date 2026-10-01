package com.aliedu;

import android.view.View;

import org.json.JSONObject;
import org.json.JSONException;

/**
 * Functional interface for creating native Android Views from Pydrud JSON.
 *
 * Each registered widget type provides its own ViewCreator, making
 * the rendering pipeline extensible without modifying ViewFactory.
 */
@FunctionalInterface
public interface ViewCreator {
    /**
     * Create a native Android View from a Pydrud JSON widget description.
     *
     * @param json    The widget JSON node (contains "type", "key",
     *                "props", "style", "children", etc.)
     * @param context The Android Context (Activity).
     * @param factory The parent ViewFactory (for access to viewMap,
     *                applyStyle(), etc.)
     * @return The created View, or null if creation failed.
     * @throws JSONException If required JSON fields are missing.
     */
    View create(JSONObject json, android.content.Context context, ViewFactory factory) throws JSONException;
}

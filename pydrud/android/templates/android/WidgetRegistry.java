package com.aliedu;

import android.util.Log;

import org.json.JSONObject;
import org.json.JSONException;

import java.util.HashMap;
import java.util.Map;

/**
 * WidgetRegistry — maps Pydrud widget type names to ViewCreator instances.
 *
 * Replaces the monolithic switch statement in ViewFactory with a modular,
 * extensible map-based lookup. New widget types can be registered without
 * modifying any existing code.
 *
 * Usage::
 *
 *     WidgetRegistry reg = new WidgetRegistry();
 *     reg.register("Text", (json, ctx, factory) -> {
 *         TextView tv = new TextView(ctx);
 *         // ...
 *         return tv;
 *     });
 */
public class WidgetRegistry {

    private static final String TAG = "PydrudRegistry";

    private final Map<String, ViewCreator> creators = new HashMap<>();

    /**
     * Register a ViewCreator for a given widget type.
     *
     * @param type    The Pydrud widget type string (e.g. "Text", "Button").
     * @param creator A ViewCreator that builds a View from JSON.
     */
    public void register(String type, ViewCreator creator) {
        creators.put(type, creator);
    }

    /**
     * Look up the ViewCreator for a widget type.
     *
     * @param type The widget type string.
     * @return The registered ViewCreator, or null if not found.
     */
    public ViewCreator get(String type) {
        return creators.get(type);
    }

    /**
     * Check if a widget type is registered.
     *
     * @param type The widget type string.
     * @return true if a creator is registered for this type.
     */
    public boolean hasType(String type) {
        return creators.containsKey(type);
    }

    /**
     * Create a View for the given widget JSON using the registered creator.
     *
     * @param json    The widget JSON node.
     * @param context The Android Context.
     * @param factory The parent ViewFactory (for shared utilities).
     * @return The created View, or null if type is unknown or creation fails.
     */
    public View create(JSONObject json, android.content.Context context, ViewFactory factory) {
        try {
            String type = json.getString("type");
            ViewCreator creator = creators.get(type);
            if (creator == null) {
                Log.w(TAG, "Unknown widget type: " + type);
                return null;
            }
            return creator.create(json, context, factory);
        } catch (JSONException e) {
            Log.e(TAG, "Widget creation error", e);
            return null;
        }
    }

    /**
     * Remove a widget type registration.
     *
     * @param type The widget type to unregister.
     */
    public void unregister(String type) {
        creators.remove(type);
    }

    /**
     * Remove all registrations.
     */
    public void clear() {
        creators.clear();
    }

    /**
     * Return the number of registered widget types.
     */
    public int size() {
        return creators.size();
    }
}

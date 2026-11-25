// Use the shared list service so Finder owns the on-disk format and other
// favorites survive. With no arguments this only checks access to the list.
#import <CoreServices/CoreServices.h>
#import <Foundation/Foundation.h>

// A bookmark and a command-line path may use different case or firmlink
// spellings for the same directory on macOS.
static id directoryKey(NSURL *url) {
    id key = nil;
    [url getResourceValue:&key forKey:NSURLFileResourceIdentifierKey error:NULL];
    return key ?: url.URLByResolvingSymlinksInPath.path;
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        LSSharedFileListRef list = LSSharedFileListCreate(NULL, kLSSharedFileListFavoriteItems, NULL);
        NSArray *items = list ? CFBridgingRelease(LSSharedFileListCopySnapshot(list, NULL)) : nil;
        if (!items) {
            fprintf(stderr, "Cannot read Finder Favorites. Open Finder and try again.\n");
            return 1;
        }

        NSMutableDictionary *existing = [NSMutableDictionary dictionary];
        for (id entry in items) {
            LSSharedFileListItemRef item = (__bridge LSSharedFileListItemRef)entry;
            NSURL *url = CFBridgingRelease(LSSharedFileListItemCopyResolvedURL(item,
                kLSSharedFileListNoUserInteraction | kLSSharedFileListDoNotMountVolumes, NULL));
            if (url.isFileURL) {
                existing[directoryKey(url)] = entry;
            }
        }
        int status = 0;
        for (int i = 1; i < argc; i++) {
            NSURL *url = [NSURL fileURLWithFileSystemRepresentation:argv[i]
                isDirectory:YES relativeToURL:nil];
            LSSharedFileListItemRef item = (__bridge LSSharedFileListItemRef)existing[directoryKey(url)];
            if (item) {
                NSNumber *hidden = CFBridgingRelease(LSSharedFileListItemCopyProperty(item, kLSSharedFileListItemHidden));
                if (!hidden.boolValue) {
                    continue;
                }
                if (LSSharedFileListItemSetProperty(item, kLSSharedFileListItemHidden, kCFBooleanFalse) == noErr) {
                    continue;
                }
            } else {
                item = LSSharedFileListInsertItemURL(list, kLSSharedFileListItemLast, NULL,
                    NULL, (__bridge CFURLRef)url, NULL, NULL);
                if (item) {
                    existing[directoryKey(url)] = CFBridgingRelease(item);
                    continue;
                }
            }
            fprintf(stderr, "Cannot add %s to Finder Favorites. Use Finder > File > Add to Sidebar.\n", argv[i]);
            status = 1;
        }
        CFRelease(list);
        return status;
    }
}

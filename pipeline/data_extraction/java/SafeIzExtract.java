import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.*;

/** Extract required SEDRE resources without running the installer. */
public class SafeIzExtract {
    static String hash(Path path) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = Files.newInputStream(path)) {
            byte[] buffer = new byte[1048576];
            for (int n; (n = in.read(buffer)) != -1;) md.update(buffer, 0, n);
        }
        StringBuilder out = new StringBuilder();
        for (byte value : md.digest()) out.append(String.format("%02x", value & 255));
        return out.toString();
    }

    static ObjectInputStream objects(InputStream stream) throws Exception {
        ObjectInputStream input = new ObjectInputStream(stream);
        input.setObjectInputFilter(info -> {
            if (info.depth() > 32 || info.references() > 200000 || info.arrayLength() > 1000000)
                return ObjectInputFilter.Status.REJECTED;
            Class<?> cls = info.serialClass();
            if (cls == null) return ObjectInputFilter.Status.UNDECIDED;
            while (cls.isArray()) cls = cls.getComponentType();
            String name = cls.getName();
            return cls.isPrimitive() || name.startsWith("java.lang.") || name.startsWith("java.util.")
                || name.equals("com.izforge.izpack.PackFile") || name.equals("com.izforge.izpack.util.OsConstraint")
                ? ObjectInputFilter.Status.ALLOWED : ObjectInputFilter.Status.REJECTED;
        });
        return input;
    }

    static Path checked(Path root, Path path) throws Exception {
        path = path.toAbsolutePath().normalize();
        if (!path.startsWith(root)) throw new IOException("Output outside workspace");
        for (Path node = path; node != null && node.startsWith(root); node = node.getParent())
            if (Files.isSymbolicLink(node)) throw new IOException("Linked output path: " + node);
        return path;
    }

    static String relative(String target) throws Exception {
        target = target.replace('\\', '/');
        if (target.startsWith("$INSTALL_PATH/")) target = target.substring(14);
        else if (target.equals("$INSTALL_PATH")) return "";
        if (target.startsWith("/") || target.contains(":") || target.contains("$") || target.contains("\t") || target.contains("\n"))
            throw new IOException("Invalid installer path");
        for (String part : target.split("/")) if (part.equals("..")) throw new IOException("Parent traversal");
        return target;
    }

    public static void main(String[] args) throws Exception {
        Path jar = Paths.get(args[0]).toAbsolutePath();
        // The Python caller supplies a resolved workspace; avoid traversing OS ancestors here.
        Path root = Paths.get(args[3]).toAbsolutePath().normalize();
        if (!Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(root))
            throw new IOException("Invalid workspace directory");
        Path destination = checked(root, Paths.get(args[1]));
        Path report = checked(root, Paths.get(args[2]));
        Files.createDirectories(destination);
        Files.createDirectories(report.getParent());
        Class<?> type = Class.forName("com.izforge.izpack.PackFile");
        Method getTarget = type.getMethod("getTargetPath"), length = type.getMethod("length");
        Method isDirectory = type.getMethod("isDirectory"), isReference = type.getMethod("isBackReference");
        Field previousPack = type.getField("previousPackNumber"), previousOffset = type.getField("offsetInPreviousPack");
        int copied = 0, references = 0;
        try (ZipFile zip = new ZipFile(jar.toFile());
             PrintWriter manifest = new PrintWriter(Files.newBufferedWriter(report, java.nio.charset.StandardCharsets.UTF_8))) {
            List<String> packs = new ArrayList<>();
            zip.stream().filter(e -> e.getName().matches("packs/pack[0-9]+"))
                .forEach(e -> packs.add(e.getName()));
            packs.sort(Comparator.comparingInt(p -> Integer.parseInt(p.substring(10))));
            if (packs.isEmpty()) throw new IOException("No IzPack packs");
            for (String pack : packs) {
                try (ObjectInputStream input = objects(new BufferedInputStream(zip.getInputStream(zip.getEntry(pack))))) {
                    int count = input.readInt();
                    if (count < 0 || count > 1000000) throw new IOException("Invalid pack count");
                    System.out.println(pack + ": " + count + " entries");
                    for (int index = 0; index < count; index++) {
                        Object item = input.readObject();
                        if (!type.isInstance(item)) throw new IOException("Unexpected pack metadata");
                        boolean directory = (Boolean)isDirectory.invoke(item);
                        boolean reference = (Boolean)isReference.invoke(item);
                        String rel = relative((String)getTarget.invoke(item));
                        long size = (Long)length.invoke(item);
                        if (size < 0) throw new IOException("Negative size");
                        if (directory) continue;
                        boolean wanted = rel.startsWith("Properties/") || rel.startsWith("Resources/")
                            || rel.equalsIgnoreCase("Firebird/SDR.FDB");
                        OutputStream output = OutputStream.nullOutputStream();
                        Path target = null, part = null;
                        if (wanted) {
                            target = checked(root, destination.resolve(rel));
                            Files.createDirectories(target.getParent());
                            part = checked(root, target.resolveSibling(target.getFileName() + ".part"));
                            Files.deleteIfExists(part);
                            output = Files.newOutputStream(part, StandardOpenOption.CREATE_NEW);
                        }
                        try (OutputStream out = output) {
                            if (reference) {
                                if (wanted) {
                                    ZipEntry earlier = zip.getEntry("packs/pack" + previousPack.getInt(item));
                                    if (earlier == null || previousOffset.getLong(item) < 4) throw new IOException("Invalid backreference");
                                    try (InputStream raw = zip.getInputStream(earlier);
                                         ObjectInputStream other = objects(raw)) {
                                        raw.skipNBytes(previousOffset.getLong(item) - 4);
                                        transfer(other, out, size);
                                    }
                                    references++;
                                }
                            } else {
                                transfer(input, out, size);
                            }
                        }
                        if (wanted) {
                            if (Files.size(part) != size) throw new IOException("Extracted size mismatch");
                            if (Files.exists(target)) {
                                Path quarantine = checked(root, root.resolve("quarantine/setup-installer/" + UUID.randomUUID())
                                    .resolve(root.relativize(target)));
                                Files.createDirectories(quarantine.getParent());
                                Files.move(target, quarantine);
                            }
                            Files.move(part, target);
                            manifest.println(rel + "\t" + size + "\t" + hash(target));
                            manifest.flush();
                            copied++;
                        }
                        if ((index + 1) % 100 == 0) System.out.println("  " + (index + 1) + "/" + count + " entries; extracted=" + copied);
                    }
                }
            }
        }
        System.out.println("Installer extracted: " + copied + " files; backreferences=" + references);
    }

    static void transfer(InputStream input, OutputStream output, long remaining) throws Exception {
        byte[] buffer = new byte[1048576];
        while (remaining > 0) {
            int read = input.read(buffer, 0, (int)Math.min(buffer.length, remaining));
            if (read < 0) throw new EOFException("Truncated pack payload");
            output.write(buffer, 0, read);
            remaining -= read;
        }
    }
}

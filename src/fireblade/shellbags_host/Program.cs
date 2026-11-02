using System.Globalization;
using System.Text;
using ExtensionBlocks;
using Registry;
using Registry.Abstractions;
using Registry.Other;

// Offline traversal only; no access to the live Windows Registry or file targets.
internal static class Program
{
    static string[] Roots = {
        @"Local Settings\Software\Microsoft\Windows\Shell\BagMRU",
        @"Local Settings\Software\Microsoft\Windows\ShellNoRoam\BagMRU",
        @"Software\Microsoft\Windows\Shell\BagMRU",
        @"Software\Microsoft\Windows\ShellNoRoam\BagMRU",
        @"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU"
    };
    static int Main(string[] args)
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        if (args.Contains("--help")) { Console.WriteLine("Fireblade Shellbags: -f <offline hive> --csv <output directory>"); return 0; }
        try {
            string Option(string key) { var i=Array.IndexOf(args,key); if(i<0 || i+1>=args.Length)throw new ArgumentException("Missing "+key); return args[i+1]; }
            var source=Path.GetFullPath(Option("-f"));var output=Path.GetFullPath(Option("--csv"));
            if(new FileInfo(source).Length>512L*1024*1024)throw new Exception("Hive exceeds 512 MiB Shellbags limit");
            Directory.CreateDirectory(output);
            var hive=new RegistryHive(File.ReadAllBytes(source),source){RecoverDeleted=false};
            if(hive.Header.PrimarySequenceNumber!=hive.Header.SecondarySequenceNumber || !hive.Header.ValidateCheckSum()) {
                var logs=Directory.EnumerateFiles(Path.GetDirectoryName(source)!).Where(p=>
                    (p.Equals(source+".LOG1",StringComparison.OrdinalIgnoreCase)||p.Equals(source+".LOG2",StringComparison.OrdinalIgnoreCase)) &&
                    !File.GetAttributes(p).HasFlag(FileAttributes.ReparsePoint)).ToList();
                if(logs.Count>0)hive.ProcessTransactionLogs(logs.Select(p=>new TransactionLogFileInfo(p,File.ReadAllBytes(p))).ToList(),true);
                if(hive.Header.PrimarySequenceNumber!=hive.Header.SecondarySequenceNumber || !hive.Header.ValidateCheckSum())
                    Console.WriteLine("[WRN] Dirty hive or invalid checksum: Shellbags reflect the readable base; transaction recovery was unavailable or incomplete.");
            }
            if(!hive.ParseHive())throw new Exception("Hive could not be parsed");
            using var writer=new StreamWriter(Path.Combine(output,"Shellbags.csv"),false,new UTF8Encoding(false));
            void Row(params object?[] cells)=>writer.WriteLine(string.Join(",",cells.Select(cell=>"\""+(Convert.ToString(cell,CultureInfo.InvariantCulture)??"").Replace("\"","\"\"")+"\"")));
            Row("Path","Value","ShellItemType","MRUPosition","NodeSlot","BagMRUKeyLastWriteUtc","ShellItemModified","ShellItemCreated","ShellItemAccessed","Status","RegistryKey","ValueName","SourceHive","RawHex");
            int count=0;var visited=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach(var root in Roots) {
                var key=hive.GetKey(root);if(key==null)continue;
                var pending=new Stack<(RegistryKey Key,string Parent,int Depth)>();pending.Push((key,"",0));
                while(pending.Count>0) {
                    var (current,parent,depth)=pending.Pop();
                    if(!visited.Add(current.KeyPath))continue;
                    if(visited.Count>1000000 || depth>512)throw new Exception("Shellbags key/depth limit reached");
                    var mru=current.Values.FirstOrDefault(v=>v.ValueName.Equals("MRUListEx",StringComparison.OrdinalIgnoreCase))?.ValueDataRaw??Array.Empty<byte>();
                    var order=new List<uint>();for(int i=0;i+4<=mru.Length;i+=4){var n=BitConverter.ToUInt32(mru,i);if(n==uint.MaxValue)break;order.Add(n);}
                    var byName=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
                    foreach(var value in current.Values.Where(v=>uint.TryParse(v.ValueName,out _))) {
                        var raw=value.ValueDataRaw;var status="Parsed";string name="",type="",modified="",created="",accessed="";
                        try {
                            var bag=ShellItemFactory.Create(raw,int.Parse(value.ValueName),order.IndexOf(uint.Parse(value.ValueName)),current.KeyPath);
                            name=bag.Value;type=bag.GetType().Name;
                            if(type=="ShellBagUnknown" || string.IsNullOrWhiteSpace(name))status="Unknown";
                            string Property(object obj,string property)=>Format(obj.GetType().GetProperty(property)?.GetValue(obj));
                            modified=Property(bag,"LastModificationTime");created=Property(bag,"CreatedOnTime");accessed=Property(bag,"LastAccessTime");
                            foreach(var extension in bag.ExtensionBlocks??new()) {
                                var longName=Property(extension,"LongName");if(!string.IsNullOrEmpty(longName))name=longName;
                                var c=Property(extension,"CreatedOnTime");if(c!="")created=c;
                                var a=Property(extension,"LastAccessTime");if(a!="")accessed=a;
                            }
                        } catch(Exception ex){status="Damaged";Console.WriteLine("[WRN] Shell item "+current.KeyPath+"\\"+value.ValueName+": "+ex.Message);}
                        if(status=="Unknown")Console.WriteLine("[WRN] Unknown shell item "+current.KeyPath+"\\"+value.ValueName);
                        if(string.IsNullOrWhiteSpace(name))name="["+status+" item "+value.ValueName+"]";
                        var path=parent.Length==0?name:parent.TrimEnd('\\')+"\\"+name;byName[value.ValueName]=path;
                        var child=current.SubKeys.FirstOrDefault(k=>k.KeyName==value.ValueName);
                        var node=child?.Values.FirstOrDefault(v=>v.ValueName.Equals("NodeSlot",StringComparison.OrdinalIgnoreCase))?.ValueData;
                        Row(path,name,type,order.IndexOf(uint.Parse(value.ValueName)),node,
                            Format(current.LastWriteTime),modified,created,accessed,status,current.KeyPath,value.ValueName,source,Convert.ToHexString(raw));count++;
                    }
                    foreach(var child in current.SubKeys.Where(k=>uint.TryParse(k.KeyName,out _))) {
                        var childPath=byName.GetValueOrDefault(child.KeyName,parent+"\\[missing value "+child.KeyName+"]");
                        pending.Push((child,childPath,depth+1));
                    }
                }
            }
            Console.WriteLine("Shellbags records: "+count);return 0;
        } catch(Exception ex){Console.Error.WriteLine(ex.Message);return 1;}
    }
    static string Format(object? value)=>value switch {
        DateTimeOffset date=>date.ToString("O",CultureInfo.InvariantCulture),
        DateTime date=>date.ToString("O",CultureInfo.InvariantCulture),
        null=>"",_=>Convert.ToString(value,CultureInfo.InvariantCulture)??""
    };
}

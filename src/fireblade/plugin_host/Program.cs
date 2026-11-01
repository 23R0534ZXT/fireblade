using System.Collections;
using System.ComponentModel;
using System.Globalization;
using System.Reflection;
#if !NETFRAMEWORK
using System.Runtime.Loader;
#endif
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

internal static class Program
{
    static readonly JsonSerializerOptions Json = new() { WriteIndented = false, IncludeFields = true };
    static Assembly Load(string path)
    {
        path = Path.GetFullPath(path);
        var folder = Path.GetDirectoryName(path)!;
#if NETFRAMEWORK
        AppDomain.CurrentDomain.AssemblyResolve += (_, args) =>
        {
            var name=new AssemblyName(args.Name);
            foreach(var directory in new[]{folder,Path.GetDirectoryName(folder) ?? folder}) {
                var candidate=Path.Combine(directory,name.Name+".dll");
                if(File.Exists(candidate))return Assembly.LoadFrom(candidate);
            }
            return null;
        };
        return Assembly.LoadFrom(path);
#else
        AssemblyLoadContext.Default.Resolving += (_, name) =>
        {
            foreach(var directory in new[]{folder,Path.GetDirectoryName(folder) ?? folder}) {
                var candidate=Path.Combine(directory,name.Name+".dll");
                if(File.Exists(candidate))return AssemblyLoadContext.Default.LoadFromAssemblyPath(candidate);
            }
            return null;
        };
        return AssemblyLoadContext.Default.LoadFromAssemblyPath(path);
#endif
    }
    static IEnumerable<Type> Types(Assembly assembly)
    {
        try { return assembly.GetTypes(); }
        catch (ReflectionTypeLoadException e)
        {
            var details=string.Join("; ",e.LoaderExceptions.Select(x=>x?.Message));
            throw new InvalidOperationException("Dépendances du plugin manquantes/incompatibles : "+details,e);
        }
    }
    static Type? ReaderContract(Type type)=>type.GetInterfaces().Append(type).FirstOrDefault(t=>t.GetMethod("ProcessFile",[typeof(string)])!=null && t.GetProperty("DataList")!=null);
    static bool IsReader(Type type) => type.IsClass && !type.IsAbstract && type.GetConstructor(Type.EmptyTypes)!=null && ReaderContract(type)!=null;
    static object Inspect(Assembly assembly) => Types(assembly).Where(IsReader).Select(type =>
    {
        var reader=Activator.CreateInstance(type)!;var contract=ReaderContract(type)!;
        return new {
            type=type.FullName,
            description=contract.GetProperty("FileDescription")?.GetValue(reader)?.ToString() ?? type.Name,
            author=contract.GetProperty("Author")?.GetValue(reader)?.ToString(),
            headers=(contract.GetProperty("ExpectedHeaders")?.GetValue(reader) as IEnumerable)?.Cast<object>().Select(x=>x.ToString()).ToArray()
        };
    }).ToArray();
    static string ObjectCell(object value) {
        try {return JsonSerializer.Serialize(value,Json);}
        catch(NotSupportedException) {return value.ToString() ?? "";}
        catch(JsonException) {return value.ToString() ?? "";}
    }
    static string Cell(object? value) => value switch
    {
        null => "",
        string text => text,
#if !NETFRAMEWORK
        DateOnly d => d.ToString("yyyy-MM-dd",CultureInfo.InvariantCulture),
        TimeOnly d => d.ToString("HH:mm:ss.fffffff",CultureInfo.InvariantCulture),
#endif
        DateTime d => d.ToString("O",CultureInfo.InvariantCulture),
        DateTimeOffset d => d.ToString("O",CultureInfo.InvariantCulture),
        IEnumerable list when value is not string => ObjectCell(value),
        IFormattable f => f.ToString(null,CultureInfo.InvariantCulture) ?? "",
        _ => ObjectCell(value)
    };
    static void Record(TextWriter output, IEnumerable<string> cells)
    {
        output.WriteLine(string.Join(",",cells.Select(value=>"\""+value.Replace("\"","\"\"")+"\"")));
    }
    static (object reader,IEnumerable data,Type contract) ReadObjects(Assembly assembly,string typeName,string source)
    {
        var type=assembly.GetType(typeName,true)!;
        if(!IsReader(type))throw new InvalidOperationException("Type de lecteur TLE invalide");
        var reader=Activator.CreateInstance(type)!;var contract=ReaderContract(type)!;
        // Tag state is kept in Fireblade's analysis; plugins start without tags.
        var tags=contract.GetProperty("TaggedLines");
        if(tags?.CanWrite==true && tags.PropertyType.IsAssignableFrom(typeof(List<int>)))tags.SetValue(reader,new List<int>());
        contract.GetMethod("ProcessFile",[typeof(string)])!.Invoke(reader,[Path.GetFullPath(source)]);
        var data=contract.GetProperty("DataList")!.GetValue(reader) as IEnumerable ?? throw new InvalidOperationException("DataList du plugin n’est pas une collection");
        return (reader,data,contract);
    }
    static bool ComplexType(Type type) {
        type=Nullable.GetUnderlyingType(type) ?? type;
        return !(type.IsPrimitive || type==typeof(string) || type==typeof(decimal) || type==typeof(DateTime) || type==typeof(DateTimeOffset));
    }
    static object ConvertFile(Assembly assembly,string typeName,string source,string target)
    {
        var type=assembly.GetType(typeName,true)!;
        if(!IsReader(type))throw new InvalidOperationException("Type de lecteur TLE invalide");
        var (reader,data,contract)=ReadObjects(assembly,typeName,source);
        PropertyDescriptorCollection? columns=null;
        var listType=contract.GetProperty("DataList")!.PropertyType;
        var typed=contract.GetProperty("DataList")!.GetValue(reader) as ITypedList;
        if(typed!=null)columns=typed.GetItemProperties(null);
        if(columns==null || columns.Count==0)
        {
            var generic=data.GetType().GetInterfaces().Append(data.GetType()).FirstOrDefault(t=>t.IsGenericType && t.GetGenericTypeDefinition()==typeof(IList<>));
            if(generic!=null)columns=TypeDescriptor.GetProperties(generic.GetGenericArguments()[0]);
        }
        long count=0;
        using var file=new FileStream(target,FileMode.CreateNew,FileAccess.Write,FileShare.None);
        using var output=new StreamWriter(file,new UTF8Encoding(true));
        string[]? names=null;string[]? types=null;bool[]? complex=null;
        foreach(var row in data)
        {
            if(row==null)throw new InvalidOperationException("Enregistrement null dans le plugin");
            var dictionary=row as IDictionary<string,object>;
            if(names==null)
            {
                if(dictionary!=null) {names=dictionary.Keys.ToArray();types=names.Select(n=>dictionary[n]?.GetType().FullName ?? "System.Object").ToArray();}
                else {
                    if(columns==null || columns.Count==0)columns=TypeDescriptor.GetProperties(row);
                    names=columns.Cast<PropertyDescriptor>().Select(p=>p.Name).ToArray();
                    types=columns.Cast<PropertyDescriptor>().Select(p=>p.PropertyType.FullName ?? "System.String").ToArray();
                }
                complex=names.Select((n,i)=>dictionary!=null ? dictionary[n]==null || ComplexType(dictionary[n]!.GetType()) : ComplexType(columns![n]!.PropertyType)).ToArray();
                if(names.Length==0)throw new InvalidOperationException("Schéma du plugin vide");
                // The native grid owns editable tags. Preserve plugin line IDs as evidence.
                var visible=names.Select(n=>n=="Line"?"TLE_SourceLine":n).Where(n=>n!="Tag");
                Record(output,visible);
            }
            Record(output,names.Where(n=>n!="Tag").Select(n=>Cell(dictionary!=null ? (dictionary.TryGetValue(n,out var field) ? field : null) : columns![n]!.GetValue(row))));count++;
        }
        if(names==null)
        {
            if(columns!=null && columns.Count>0) {names=columns.Cast<PropertyDescriptor>().Select(p=>p.Name).ToArray();types=columns.Cast<PropertyDescriptor>().Select(p=>p.PropertyType.FullName ?? "System.String").ToArray();}
            else if(type.FullName=="TLEFileGenericCsv.GenericCsv") {
                using var text=new StreamReader(source,true);
                string? first=text.ReadLine();if(first?.StartsWith("#TYPE")==true)first=text.ReadLine();
                if(first==null)throw new InvalidOperationException("CSV sans en-tête");
                var delimiter=new[]{',','\t','|',';'}.OrderByDescending(d=>first.Count(c=>c==d)).First();
                using var parser=new Microsoft.VisualBasic.FileIO.TextFieldParser(new StringReader(first));parser.SetDelimiters(delimiter.ToString());parser.HasFieldsEnclosedInQuotes=true;
                names=(parser.ReadFields() ?? []).Where(n=>!string.IsNullOrWhiteSpace(n)).Distinct().Concat(new[]{"Line","Tag"}).ToArray();
                types=names.Select(_=>"System.String").ToArray();
            }
            else throw new InvalidOperationException("Schéma de sortie vide ou inconnu");
            Record(output,names.Where(n=>n!="Tag").Select(n=>n=="Line"?"TLE_SourceLine":n));
        }
        output.Flush();
        return new { rows=count, columns=names.Select((n,i)=>new {name=n=="Line"?"TLE_SourceLine":n,type=types![i],source_name=n,complex=complex!=null && complex[i]}).Where(c=>c.name!="Tag").ToArray() };
    }
    static Dictionary<string,(object instance,MethodInfo method)> Functions(Assembly assembly)
    {
        var result=new Dictionary<string,(object,MethodInfo)>(StringComparer.OrdinalIgnoreCase);
        foreach(var type in Types(assembly).Where(t=>t.IsClass && !t.IsAbstract))
        {
            var contract=type.GetInterfaces().Append(type).FirstOrDefault(t=>t.GetMethod("Evaluate",[typeof(object[])])!=null && t.GetProperty("Name")!=null);
            if(contract==null)continue;
            var instance=Activator.CreateInstance(type)!;
            var name=contract.GetProperty("Name")!.GetValue(instance)?.ToString();
            if(name is null || string.IsNullOrWhiteSpace(name))continue;
            if(result.ContainsKey(name))throw new InvalidOperationException("Nom de fonction dupliqué : "+name);
            result.Add(name,(instance,contract.GetMethod("Evaluate",[typeof(object[])])!));
        }
        return result;
    }
    static string FunctionKind((object instance,MethodInfo method) function)
    {
        try {
            var contract=function.method.DeclaringType!;
            var method=contract.GetMethod("ResultType",[typeof(Type[])]) ?? function.instance.GetType().GetMethod("ResultType",[typeof(Type[])]);
            var type=method?.Invoke(function.instance,[Array.Empty<Type>()]) as Type;
            type=type==null ? null : Nullable.GetUnderlyingType(type) ?? type;
            if(type==typeof(bool))return "boolean";
            if(type==typeof(DateTime) || type==typeof(DateTimeOffset))return "date";
            if(type!=null && new[]{typeof(byte),typeof(short),typeof(int),typeof(long),typeof(ushort),typeof(uint),typeof(ulong),typeof(float),typeof(double),typeof(decimal)}.Contains(type))return "number";
        }catch { }
        return "text";
    }
    sealed class ObjectState {
        public IList? Rows;
        public object? Reader;
        public readonly Dictionary<string,object?> Handles=new();
        public object? Resolve(JsonElement value,HashSet<string> used,int depth=0) {
            if(depth>32)throw new InvalidOperationException("Référence CLR trop profonde");
            if(value.ValueKind!=JsonValueKind.Object || !value.TryGetProperty("$fb_type",out var tag))return Operand(value);
            if(tag.GetString()=="clr_handle") {
                var key=value.GetProperty("value").GetString()!;
                if(!Handles.TryGetValue(key,out var target))throw new InvalidOperationException("Référence CLR expirée ou étrangère");
                used.Add(key);return target;
            }
            if(tag.GetString()=="clr_column") {
                if(Rows==null)throw new InvalidOperationException("Lecteur CLR non chargé");
                var row=value.GetProperty("row").GetInt64();
                if(row<1 || row>Rows.Count)throw new InvalidOperationException("Enregistrement CLR absent");
                return Member(Rows[(int)row-1],value.GetProperty("column").GetString()!);
            }
            if(tag.GetString()=="clr_single") {
                var target=Resolve(value.GetProperty("parent"),used,depth+1);
                if(target==null)return null;
                if(target is not IEnumerable collection)throw new InvalidOperationException("Single : collection CLR requise");
                var enumerator=collection.GetEnumerator();
                try {if(!enumerator.MoveNext())return null;var item=enumerator.Current;if(enumerator.MoveNext())throw new InvalidOperationException("Single : plusieurs objets correspondent");return item;}
                finally {(enumerator as IDisposable)?.Dispose();}
            }
            if(tag.GetString()=="clr_path") {
                var target=Resolve(value.GetProperty("parent"),used,depth+1);
                var path=value.GetProperty("path").GetString()!;
                int at=path.StartsWith("$") ? 1 : 0;
                while(at<path.Length) {
                    string member;
                    if(path[at]=='.') {
                        at++;
                        if(at<path.Length && path[at]=='"') {
                            var start=at++;bool escaped=false;
                            while(at<path.Length) {var c=path[at++];if(c=='"' && !escaped)break;escaped=c=='\\' && !escaped;}
                            member=JsonSerializer.Deserialize<string>(path.Substring(start,at-start))!;
                        } else {var start=at;while(at<path.Length && path[at]!='.' && path[at]!='[')at++;member=path.Substring(start,at-start);}
                    } else if(path[at]=='[') {
                        var end=path.IndexOf(']',at);if(end<0)throw new InvalidOperationException("Chemin CLR invalide");
                        member=path.Substring(at+1,end-at-1);at=end+1;
                    } else throw new InvalidOperationException("Chemin CLR non pris en charge");
                    target=Member(target,member);
                }
                return target;
            }
            return Operand(value);
        }
        static object? Member(object? target,string name) {
            if(target==null)return null;
            if(target is IDictionary<string,object> generic && generic.TryGetValue(name,out var member))return member;
            if(target is IDictionary dictionary && dictionary.Contains(name))return dictionary[name];
            if(target is IList list && int.TryParse(name,out var index))return index>=0 && index<list.Count ? list[index] : throw new InvalidOperationException("Indice CLR absent");
            var property=TypeDescriptor.GetProperties(target).Find(name,false);
            if(property!=null)return property.GetValue(target);
            var field=target.GetType().GetField(name,BindingFlags.Instance|BindingFlags.Public);
            if(field!=null)return field.GetValue(target);
            throw new InvalidOperationException("Membre CLR absent : "+name);
        }
        public object Reference(object? target) {
            if(Handles.Count>=65536)throw new InvalidOperationException("Trop de résultats CLR simultanés (65536 maximum)");
            var key=Guid.NewGuid().ToString("N");Handles.Add(key,target);
            return new Dictionary<string,object?>{{"$fb_type","clr_handle"},{"value",key}};
        }
    }
    static void VerifyFile(string path,string expected) {
        using var stream=File.OpenRead(path);using var hash=SHA256.Create();
        var actual=BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
        if(actual!=expected)throw new InvalidOperationException("Source ou DLL CLR absente/modifiée : "+path);
    }
    static object? Operand(JsonElement value)
    {
        if(value.ValueKind==JsonValueKind.Object && value.TryGetProperty("$fb_type",out var tag))
        {
            var content=value.GetProperty("value");if(content.ValueKind==JsonValueKind.Null)return null;
            var text=content.GetString()!;
            if(tag.GetString() is "date" or "dateoffset" or "timeonly")text=System.Text.RegularExpressions.Regex.Replace(text,@"(\.\d{7})\d+","$1");
            return tag.GetString() switch {
                "guid" => Guid.Parse(text),
                "char" => text.Length==1 ? text[0] : throw new InvalidOperationException("Un caractère CLR requis"),
#if NETFRAMEWORK
                "dateonly" or "timeonly" => throw new InvalidOperationException("DateOnly/TimeOnly nécessitent le CLR moderne"),
#else
                "dateonly" => DateOnly.Parse(text.Substring(0,10),CultureInfo.InvariantCulture),
                "timeonly" => TimeOnly.Parse(text,CultureInfo.InvariantCulture),
#endif
                "date" => DateTime.Parse(text,CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind),
                "dateoffset" => DateTimeOffset.Parse(text,CultureInfo.InvariantCulture),
                "i64" => long.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u64" => ulong.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "i32" => int.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u32" => uint.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "i16" => short.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u16" => ushort.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "u8" => byte.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "decimal" => decimal.Parse(text,NumberStyles.Any,CultureInfo.InvariantCulture),
                "double" => double.Parse(text,CultureInfo.InvariantCulture),
                "single" => float.Parse(text,CultureInfo.InvariantCulture),
                "bool" => bool.Parse(text),
                _ => throw new InvalidOperationException("Type d’argument .NET inconnu")
            };
        }
        return value.ValueKind switch {
        JsonValueKind.Null => null,
        JsonValueKind.True => true,JsonValueKind.False => false,
        JsonValueKind.String => value.GetString(),
        JsonValueKind.Number => value.TryGetInt64(out var i) ? (object)i : value.TryGetDecimal(out var d) ? (object)d : value.GetDouble(),
        _ => value.Clone()
        };
    }
    static int Serve(Assembly assembly,TextWriter output)
    {
        var functions=Functions(assembly);var state=new ObjectState();
        output.WriteLine(JsonSerializer.Serialize(new {ready=true,functions=functions.Keys.ToArray(),types=functions.ToDictionary(p=>p.Key,p=>FunctionKind(p.Value))},Json));output.Flush();
        string? line;
        while((line=Console.ReadLine())!=null)
        {
            var used=new HashSet<string>();
            try {
                using var request=JsonDocument.Parse(line);var root=request.RootElement;
                var op=root.TryGetProperty("op",out var command) ? command.GetString() : "evaluate";
                if(op=="load_reader") {
                    if(state.Rows!=null)throw new InvalidOperationException("Un lecteur CLR est déjà chargé");
                    var path=root.GetProperty("path").GetString()!;var source=root.GetProperty("source").GetString()!;
                    VerifyFile(path,root.GetProperty("sha256").GetString()!);VerifyFile(source,root.GetProperty("source_sha256").GetString()!);
                    var readerAssembly=Load(path);VerifyFile(readerAssembly.Location,root.GetProperty("sha256").GetString()!);
                    var (reader,data,contract)=ReadObjects(readerAssembly,root.GetProperty("type").GetString()!,source);
                    VerifyFile(path,root.GetProperty("sha256").GetString()!);VerifyFile(source,root.GetProperty("source_sha256").GetString()!);
                    var rows=data as IList ?? data.Cast<object>().ToList();
                    if(rows.Count!=root.GetProperty("rows").GetInt64())throw new InvalidOperationException("Comptage du lecteur CLR différent de l’import");
                    state.Reader=reader;state.Rows=rows;
                    output.WriteLine("{\"loaded\":true}");
                } else if(op=="load_functions") {
                    var path=root.GetProperty("path").GetString()!;VerifyFile(path,root.GetProperty("sha256").GetString()!);
                    var functionAssembly=Load(path);VerifyFile(functionAssembly.Location,root.GetProperty("sha256").GetString()!);
                    var loaded=Functions(functionAssembly);
                    foreach(var name in loaded.Keys)if(functions.ContainsKey(name))throw new InvalidOperationException("Fonction CLR dupliquée : "+name);
                    foreach(var item in loaded)functions.Add(item.Key,item.Value);
                    output.WriteLine("{\"loaded\":true}");
                } else if(op=="clear_handles") {state.Handles.Clear();output.WriteLine("{\"cleared\":true}");}
                else {
                    var name=root.GetProperty("name").GetString()!;
                    if(!functions.TryGetValue(name,out var function))throw new InvalidOperationException("Fonction non chargée : "+name);
                    var args=root.GetProperty("arguments").EnumerateArray().Select(v=>state.Resolve(v,used)).ToArray();
                    var value=function.method.Invoke(function.instance,[args]);
                    if(root.TryGetProperty("reference",out var reference) && reference.GetBoolean())output.WriteLine(JsonSerializer.Serialize(new {operand=state.Reference(value)},Json));
                    else output.WriteLine(JsonSerializer.Serialize(new {value=value is null ? null : Cell(value)},Json));
                }
            } catch(Exception e) {output.WriteLine(JsonSerializer.Serialize(new {error=(e.InnerException ?? e).Message},Json));}
            finally {foreach(var key in used)state.Handles.Remove(key);}
            output.Flush();
        }
        return 0;
    }
    [STAThread]
    static int Main(string[] args)
    {
        CultureInfo.CurrentCulture=CultureInfo.InvariantCulture;
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        Console.SetIn(new StreamReader(Console.OpenStandardInput(),new UTF8Encoding(false)));
        Console.SetOut(new StreamWriter(Console.OpenStandardOutput(),new UTF8Encoding(false)){AutoFlush=true});
        Console.SetError(new StreamWriter(Console.OpenStandardError(),new UTF8Encoding(false)){AutoFlush=true});
        try
        {
            if(args.Length==1 && args[0]=="--self-test")
            {
                var folder=Path.Combine(Path.GetTempPath(),"Fireblade host "+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(folder);
                try {
                    var source=Path.Combine(folder,"source.txt");File.WriteAllText(source,"évidence\n0001");
                    var info=ConvertFile(Assembly.GetExecutingAssembly(),typeof(QaReader).FullName!,source,Path.Combine(folder,"out.csv"));
                    var text=File.ReadAllText(Path.Combine(folder,"out.csv"));
                    if(!text.Contains("0001") || !text.Contains("évidence"))throw new Exception("Plugin conversion failed");
                    Console.WriteLine(JsonSerializer.Serialize(new {status="passed",result=info},Json));
                } finally {Directory.Delete(folder,true);}
                return 0;
            }
#if !NETFRAMEWORK
            if(args.Length==2 && args[0]=="framework") {
                using var input=File.OpenRead(args[1]);
                using var pe=new System.Reflection.PortableExecutable.PEReader(input);
                var metadata=System.Reflection.Metadata.PEReaderExtensions.GetMetadataReader(pe);
                string framework="";
                foreach(var handle in metadata.CustomAttributes) {
                    var attr=metadata.GetCustomAttribute(handle);var blob=metadata.GetBlobReader(attr.Value);
                    try {if(blob.ReadUInt16()==1) {var value=blob.ReadSerializedString();if(value!=null && (value.StartsWith(".NETFramework,Version=") || value.StartsWith(".NETCoreApp,Version=") || value.StartsWith(".NETStandard,Version=")))framework=value;}}catch(BadImageFormatException) { }
                }
                Console.WriteLine(JsonSerializer.Serialize(new {framework},Json));return 0;
            }
#endif
            if(args.Length<2)throw new ArgumentException("inspect DLL | convert DLL TYPE SOURCE TARGET");
            var protocol=Console.Out;
            if(args[0]=="serve")Console.SetOut(Console.Error);
            var assembly=Load(args[1]);
            if(args[0]=="serve")return Serve(assembly,protocol);
            var result=args[0] switch {
                "inspect" when args.Length==2 => Inspect(assembly),
                "functions" when args.Length==2 => Functions(assembly).Keys.ToArray(),
                "convert" when args.Length==5 => ConvertFile(assembly,args[2],args[3],args[4]),
                _ => throw new ArgumentException("Commande de plugin inconnue")
            };
            Console.WriteLine(JsonSerializer.Serialize(result,Json));return 0;
        }
        catch(Exception e) { Console.Error.WriteLine((e is TargetInvocationException ? e.InnerException ?? e : e).ToString());return 1; }
    }
}
// Tiny self-test reader; no investigator data or large CSV generator is used.
public sealed class QaReader
{
    public List<QaRow> DataList { get; } = [];
    public void ProcessFile(string path) { DataList.Add(new QaRow {Text=File.ReadAllText(path),Identifier="0001"}); }
}
public sealed class QaRow { public string Text {get;set;}=""; public string Identifier {get;set;}=""; }

public sealed class QaFunction
{
    public string Name => "QaDouble";
    public object Evaluate(params object[] values) => decimal.Parse(values[0].ToString()!,CultureInfo.InvariantCulture)*2;
}
